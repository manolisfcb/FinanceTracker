# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- builder
# Two stages so the compilers and the pip cache never reach the runtime
# image: the wheels get built here and only the installed site-packages are
# copied across.
FROM python:3.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# build-essential/libffi/libxml2 cover the few dependencies without a
# manylinux wheel for this platform (lxml and curl_cffi are the usual ones).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on its own so the dependency layer is cached until requirements.txt
# itself changes — application edits then rebuild in seconds.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# ---------------------------------------------------------------- runtime
FROM python:3.13-slim-bookworm AS runtime

# libxml2/libxslt without the -dev headers: the shared libraries lxml links
# against at run time.
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

# Non-root: nothing in here needs privileges, and a container escape should
# not land on uid 0.
RUN useradd --create-home --uid 10001 truenorth

COPY --chown=truenorth:truenorth . .

# SQLite (if that is the chosen backend) writes here; with Postgres the
# directory is simply unused. Owned by the app user either way, since the
# process cannot create it at runtime as non-root.
RUN mkdir -p /app/instance && chown truenorth:truenorth /app/instance

USER truenorth

EXPOSE 8000

# Uses the app's own /healthz, which pings the database — a web process that
# cannot reach the database is not ready, whatever the port says.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
