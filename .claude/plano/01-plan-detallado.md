# Plan Detallado de Tareas

> Convención: `[S]` = pequeña (≤2h), `[M]` = media (½–1 día), `[L]` = grande (2–4 días).
> Cada fase termina con la app corriendo y desplegable.

---

## Fase 0 — Saneamiento técnico (1–2 semanas)

### 0.1 Arquitectura
- [ ] `[M]` **App factory real**: mover creación de app a `src/__init__.py :: create_app(config)`;
      instanciar `db`, `migrate`, `login_manager`, `scheduler` en `src/extensions.py` sin app;
      `app.py` queda como entrypoint (`app = create_app()`). Elimina imports circulares.
- [ ] `[S]` Corregir `db.ForeingKey` → `db.ForeignKey` en `PortfolioSnapshots.py` y registrarlo en `src/models/__init__.py`.
- [ ] `[S]` Reemplazar SQL f-string en `src/utils/querys.py` por query parametrizada (`text(...).bindparams(user_id=...)`) o SQLAlchemy ORM.
- [ ] `[S]` Reactivar `@login_required` en `/portfolio`, `/dash`, `/stocks`; manejar usuario anónimo.
- [ ] `[S]` Separar blueprints: `auth`, `portfolio`, `stocks`, `personal_finance` (o eliminar este último del alcance — **decisión**).
- [ ] `[M]` Mover scripts sueltos de la raíz a `/scripts` (o borrar): teste.py, teste.html, binance.ipynb, PDFs, generate_*.py, upload_*.py, get_*.py.
- [ ] `[S]` `.gitignore`: agregar `instance/`, `.DS_Store`, `*.db`.

### 0.2 Seguridad y configuración
- [ ] `[S]` Quitar defaults `'xxx'` de SECRET_KEY/JWT_SECRET_KEY → fallar si faltan en producción.
- [ ] `[S]` Quitar `app.config["DEBUG"] = True` global; respetar config por entorno.
- [ ] `[S]` `.env.example` documentando todas las variables.

### 0.3 Limpieza Brasil
- [ ] `[S]` Eliminar `src/utils/brfinance/` y `check_stocks_news.py` (CVM).
- [ ] `[S]` Quitar `cvm_code` de StockModel (migración Alembic).
- [ ] `[S]` Archivar `TicketModel.csv` (tickers .SA) en `/scripts/legacy`.
- [ ] `[M]` Renombrar dominio: `TransactionModel` (gastos) vs. futuro módulo de inversiones — evitar colisión de nombres.

### 0.4 Calidad
- [ ] `[M]` Pytest + fixtures con app factory y SQLite en memoria; tests de humo para auth y portfolio.
- [ ] `[S]` GitHub Actions: lint (ruff) + tests en cada push.
- [ ] `[S]` Congelar requirements con `pip-tools` o migrar a `uv`/`pyproject.toml`.

**Criterio de salida**: la app arranca con `create_app()`, tests verdes, ninguna referencia a CVM/B3 en el flujo principal.

---

## Fase 1 — Universo de acciones + fundamentales (2–3 semanas)

### 1.1 Modelo de datos
- [ ] `[M]` Refactor `StockModel` → `Asset`:
      `symbol`, `yahoo_symbol` (AAPL vs RY.TO), `exchange` (TSX/TSXV/NYSE/NASDAQ), `currency` (CAD/USD),
      `name`, `sector`, `industry`, `country`, `website`, **`ir_website`**, `logo_url`, `is_active`.
      Índice único `(symbol, exchange)`.
- [ ] `[M]` Nueva tabla `Fundamentals` (1-N con Asset, snapshot con `as_of_date`):
      `market_cap, pe, forward_pe, pb, ps, ev_ebitda, roe, roa, roic, gross_margin, operating_margin,
      net_margin, debt_to_equity, current_ratio, quick_ratio, dividend_yield, payout_ratio,
      dividend_rate, eps, eps_growth_5y, revenue_growth_5y, beta, fifty_two_week_high/low, price`.
- [ ] `[S]` Tabla `DividendHistory` (asset_id, ex_date, pay_date, amount, currency).
- [ ] `[S]` Migraciones Alembic para todo lo anterior.

### 1.2 Capa de proveedores de datos
- [ ] `[L]` `src/services/market_data/` con interfaz `MarketDataProvider`
      (`get_profile`, `get_quote`, `get_fundamentals`, `get_dividends`) y primera implementación
      `YahooProvider` (yfinance). Retries/backoff centralizados, rate-limit configurable.
- [ ] `[S]` Config `MARKET_DATA_PROVIDER=yahoo|eodhd|fmp` para swap futuro.

### 1.3 Seed del universo CA/US
- [ ] `[M]` Script `scripts/seed_universe.py`: cargar emisores TSX/TSXV desde los listados de
      TMX Group + S&P500/NASDAQ100 para US (fuente CSV pública). Normalizar símbolo Yahoo (`.TO`, `.V`).
- [ ] `[M]` Enriquecer cada asset con perfil yfinance (sector, industria, website) en batch con
      ThreadPool + rate limit.
- [ ] `[M]` Campo `ir_website`: heurística (website + `/investors`|`/investor-relations`) + verificación
      HTTP + posibilidad de corrección manual vía admin.

### 1.4 Jobs de actualización
- [ ] `[M]` Job diario `refresh_fundamentals` (después del cierre de mercado, 18:00 ET) — inserta snapshot en `Fundamentals`.
- [ ] `[S]` Job cada 15 min en horario de mercado `refresh_quotes` (solo precio) para assets en portafolios.
- [ ] `[S]` Job diario FX: tasa CAD/USD (Banco de Canadá tiene [API pública de valet](https://www.bankofcanada.ca/valet/docs)) → tabla `FxRate`.
- [ ] `[S]` Logging estructurado + tabla `JobRun` (job, started, finished, status, items) para monitoreo.

### 1.5 Screener (pantalla "Acciones")
- [ ] `[L]` Ruta `/stocks`: tabla server-rendered con HTMX — columnas: symbol, nombre, exchange,
      sector, precio, P/E, P/B, ROE, D/E, DY, payout, market cap. Orden por columna, paginación,
      filtros (exchange, sector, rangos de indicadores), búsqueda por nombre/símbolo.
- [ ] `[S]` Export CSV del screener filtrado.

**Criterio de salida**: universo ≥ 500 empresas CA + índices US sembrado; screener navegable con fundamentales reales actualizados a diario.

---

## Fase 2 — Página de empresa (1–2 semanas)

- [ ] `[L]` Ruta `/stocks/<exchange>/<symbol>`:
      - Header: logo, nombre, symbol, exchange, sector, precio + variación día, botón "IR site" y "Website".
      - Grid de indicadores (los de Fundamentals) agrupados: Valuación / Rentabilidad / Endeudamiento / Dividendos.
      - Gráfico de precio histórico (1M/6M/1Y/5Y) — endpoint JSON + Chart.js.
      - Historial de dividendos (tabla + gráfico anual).
      - Descripción de la empresa (longBusinessSummary de yfinance).
- [ ] `[M]` Endpoint `/api/assets/<id>/prices?range=` con caching (tabla `PriceHistory` EOD o fetch on-demand con cache).
- [ ] `[S]` Botón "Agregar a portafolio" → modal de nueva orden pre-llenado.
- [ ] `[S]` SEO/UX: breadcrumbs, estados de carga HTMX, empty states.

**Criterio de salida**: cualquier empresa del universo tiene página completa tipo Suno Analítica.

---

## Fase 3 — Portafolio v2 (2–3 semanas)

### 3.1 Dominio
- [ ] `[M]` Rediseño `Order`: agregar `fees`, `currency`, `fx_rate_to_cad`, `account`
      (TFSA/RRSP/Margin/Cash — cuentas registradas canadienses), `broker`.
- [ ] `[L]` Servicio `PortfolioService`: recalcular posiciones desde órdenes (avg cost method — el
      método que exige la CRA es *average cost*, no FIFO), realized/unrealized P&L, en CAD y moneda original.
      Reemplaza la tabla materializada con duplicados; recalcular es idempotente.
- [ ] `[M]` `PortfolioSnapshot` diario (job): patrimonio, invertido, P&L, por cuenta y total.
- [ ] `[M]` Registro de dividendos recibidos (auto-sugeridos desde `DividendHistory` × posición en ex-date, confirmables por el usuario).

### 3.2 Import de brokers canadienses
- [ ] `[M]` Adaptar patrón Strategy existente: `QuestradeCSVImporter`, `WealthsimpleCSVImporter`,
      `IBKRFlexImporter` (CSV/Excel export de cada broker). Eliminar `OrdersFromB3`.
- [ ] `[S]` Pantalla de import con preview + validación de duplicados (hash de orden).
- [ ] `[S]` Entrada manual de órdenes (form + modal HTMX) con autocomplete de assets.

### 3.3 Pantallas
- [ ] `[L]` `/portfolio` (Carteira): tabla de posiciones (precio, qty, valor, costo, P.M., proventos,
      YoC, lucro, R.%), totales, gráfico donut de alocación, filtro por cuenta (TFSA/RRSP…).
- [ ] `[M]` Alocación objetivo: definir % ideal por asset/clase, mostrar desvío y "cuánto comprar".
- [ ] `[M]` `/transactions` (extrato de órdenes): filtros, edición, borrado con recálculo.
- [ ] `[M]` `/dashboard`: evolución patrimonio (snapshot), aportes mensuales, rentabilidad vs.
      benchmark (S&P/TSX Composite vía ^GSPTSE), distribución por sector/moneda/cuenta.

**Criterio de salida**: importar un CSV real de Questrade/Wealthsimple produce portafolio correcto en CAD con P&L y dividendos.

---

## Fase 4 — Proventos, calendario y hechos relevantes (2 semanas)

- [ ] `[M]` `/dividends` (Proventos): recibidos por mes (gráfico barras), YoC por posición,
      proyección próximos 12 meses, calendario de ex-dates y pay-dates de las posiciones.
- [ ] `[L]` Hechos relevantes:
      - US: job que consulta **SEC EDGAR** (API pública JSON) para 8-K/10-Q/10-K de assets en portafolio → tabla `CompanyEvent`.
      - Canadá: **SEDAR+ no tiene API pública** → empezar con feed de noticias por ticker
        (yfinance news / RSS del exchange) y link directo a la búsqueda SEDAR+ de la empresa;
        evaluar proveedor (QuoteMedia) si se vuelve crítico.
- [ ] `[M]` `/inbox`: timeline de eventos de las empresas del portafolio (dividendo anunciado, filing, resultado) con marcado leído/no leído.
- [ ] `[S]` Calendario de earnings (yfinance calendar) en página de empresa y en inbox.

---

## Fase 5 — Insights y calificación (continuo)

- [ ] `[M]` Semáforos por indicador: reglas configurables por sector (ej. P/E < mediana sector = verde).
- [ ] `[L]` Score de calidad 0–100 por empresa (ponderación de valuación/rentabilidad/deuda/dividendos), con explicación por componente.
- [ ] `[M]` Rankings: top dividend yield TSX, aristócratas canadienses (≥5 años subiendo dividendo — calculable desde `DividendHistory`), mejores ROE por sector.
- [ ] `[M]` Comparador de 2–4 empresas lado a lado.
- [ ] `[M]` Alertas por email: precio objetivo, ex-date próxima, nuevo filing.
- [ ] `[L]` (Opcional) Migrar proveedor a EODHD/FMP cuando yfinance quede corto.

---

## Fase 6 — Comunidad de inversores (2–3 semanas)

> Referencia: pestaña "Comunidade" de meusdividendos — feed continuo de análisis, dudas y
> lecturas de mercado entre inversores.

- [ ] `[M]` Modelos: `Post` (user, title, body, category, created_at), `Comment`,
      `Vote` (up/down por user+post), `PostTickerMention` (N-N post↔asset).
- [ ] `[M]` Parser de menciones `$RY`, `$ENB` en el cuerpo → chips clickeables que llevan a la
      página de la empresa; alimenta "Activos en destaque".
- [ ] `[L]` `/community`: feed con tabs **Recientes / Más votados / En alta**, categorías
      (Feed, Análisis, Dudas, Dividendos, Noticias, Operaciones, Sugerencias), composer
      ("Comparte un análisis, noticia o duda…"), votos ↑↓ y contador de comentarios (HTMX).
- [ ] `[M]` Sidebar: "Recientes" (últimas noticias de dividendos del universo) y
      "Activos en destaque" (ranking de menciones últimos 7 días).
- [ ] `[M]` Página de post con hilo de comentarios; editar/borrar propio contenido.
- [ ] `[S]` Feed por empresa: pestaña "Comunidad" dentro de la página de empresa filtrando
      posts que mencionan su ticker.
- [ ] `[S]` Moderación mínima: reporte de post, soft-delete por admin, rate-limit de publicación.
- [ ] `[S]` Barra superior de mercado (market strip) en toda la app: TSX Composite, S&P 500,
      USD/CAD, tasa BoC, estado del mercado (abierto/cerrado) — job cada 15 min.

---

## Infraestructura transversal (cuando toque)
- [ ] `[S]` Migrar SQLite → Postgres (necesario antes de multiusuario real).
- [ ] `[M]` Deploy: Docker + gunicorn; jobs APScheduler en proceso worker separado (no dentro del web worker).
- [ ] `[S]` Backups de DB + monitoreo de jobs.

## Orden recomendado de ejecución
```
Fase 0 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 4 ──► Fase 5 ──► Fase 6
(salud)   (datos)    (empresa)  (portafolio) (eventos)  (insights) (comunidad)
```
La comunidad va al final: necesita usuarios activos y páginas de empresa a las cuales enlazar
las menciones; puede adelantarse si el objetivo es validar interés temprano.
La Fase 1 va antes que el portafolio v2 porque el catálogo de assets con símbolos normalizados
es prerequisito de las órdenes multi-exchange.
