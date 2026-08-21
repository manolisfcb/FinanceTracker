# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- builder
# Dos etapas: los compiladores, uv y el árbol de build se quedan acá; a la
# imagen final solo viaja el venv ya armado.
FROM python:3.13-slim-bookworm AS builder

# binutils trae `strip`, que saca los símbolos de depuración de los .so
# (numpy, pandas, lxml, psycopg y cryptography traen ~117 MB de binarios).
RUN apt-get update && apt-get install -y --no-install-recommends \
        binutils \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# uv en vez de pip: resuelve desde uv.lock (reproducible de verdad) y, a
# diferencia de pip, no deja pip/setuptools dentro del venv que crea — 13 MB
# que no tienen nada que hacer en producción.
RUN pip install --no-cache-dir uv==0.9.26

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /build
# Solo el manifiesto y el lock: esta capa queda cacheada hasta que cambien las
# dependencias, así editar código recompila en segundos.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Adelgazado del venv. Nada de esto se usa en runtime:
#   - las suites de tests que numpy y pandas empaquetan (~84 MB). Se borran
#     los directorios llamados exactamente `tests`/`test`, nunca `testing` ni
#     `_testing`, que sí son API pública de numpy y pandas.
#   - los símbolos de depuración, PERO solo de los módulos de extensión de
#     Python (`*.cpython-*.so`). Las librerías de terceros vendorizadas
#     (numpy.libs, psycopg_binary.libs) quedan intactas: strippear el
#     OpenBLAS que numpy empaqueta lo deja ilegible —
#     "ELF load command address/offset not page-aligned" al importar numpy.
RUN find /opt/venv -type d -name tests -prune -exec rm -rf {} + \
 && find /opt/venv -type d -name test -prune -exec rm -rf {} + \
 && find /opt/venv -name '*.cpython-*.so' -print0 | xargs -0 -r strip --strip-unneeded


# ---------------------------------------------------------------- runtime
FROM python:3.13-slim-bookworm AS runtime

# Las bibliotecas compartidas contra las que enlaza lxml, sin los headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    TRUST_PROXY_HEADERS=true \
    RUN_SCHEDULER=false

WORKDIR /app

# Non-root: nada acá adentro necesita privilegios, y un escape de contenedor
# no debería aterrizar en uid 0.
RUN useradd --create-home --uid 10001 truenorth

COPY --chown=truenorth:truenorth . .

# SQLite (si alguna vez fuera el backend) escribiría acá; con Neon el
# directorio queda sin usar. Se crea en build porque el proceso no puede
# crearlo en runtime siendo non-root.
RUN mkdir -p /app/instance && chown truenorth:truenorth /app/instance

USER truenorth

EXPOSE 8000

# Liveness únicamente: /healthz no toca la base a propósito. Un sondeo cada
# 30s que consultara Neon impediría que su compute se suspenda nunca.
# Para readiness del balanceador está /readyz, que sí la consulta.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
