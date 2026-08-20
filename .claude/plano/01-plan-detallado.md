# Plan Detallado de Tareas

> Convención: `[S]` = pequeña (≤2h), `[M]` = media (½–1 día), `[L]` = grande (2–4 días).
> Cada fase termina con la app corriendo y desplegable.

---

## Fase 0 — Saneamiento técnico (1–2 semanas)

### 0.1 Arquitectura
- [x] `[M]` **App factory real**: mover creación de app a `src/__init__.py :: create_app(config)`;
      instanciar `db`, `migrate`, `login_manager`, `scheduler` en `src/extensions.py` sin app;
      `app.py` queda como entrypoint (`app = create_app()`). Elimina imports circulares.
- [x] `[S]` Corregir `db.ForeingKey` → `db.ForeignKey` en `PortfolioSnapshots.py` y registrarlo en `src/models/__init__.py`.
- [x] `[S]` Reemplazar SQL f-string en `src/utils/querys.py` por query parametrizada (`text(...).bindparams(user_id=...)`) o SQLAlchemy ORM.
- [x] `[S]` Reactivar `@login_required` en `/portfolio`, `/dash`, `/stocks`; manejar usuario anónimo.
      También en `/transactions*` (no estaban listadas pero tenían el mismo problema).
- [x] `[S]` Separar blueprints: `auth`, `portfolio`, `stocks`, `personal_finance`. **Decisión tomada 2026-08-19**:
      se mantiene `personal_finance` (transacciones/gastos) en su propio blueprint sin eliminarlo — no se borró
      funcionalidad, queda para decidir su lugar en el producto más adelante. `/dash` (patrimonio, proventos)
      se agrupó bajo `portfolio`, no `personal_finance`, porque es un dashboard de inversión, no de gastos.
- [x] `[M]` Mover scripts sueltos de la raíz a `/scripts` (`git mv`, preserva historial): teste.py, teste.html,
      binance.ipynb, documento.pdf, generate_transactions.py → `/scripts`; TicketModel.csv, cvm_1363054.pdf,
      generate_tickets.py, get_stocks_info.py, upload_orders.py, upload_current_portfolio.py, get_portfolio.py,
      schemas.py (todo lo de sabor Brasil/CVM) → `/scripts/legacy`.
- [x] `[S]` `.gitignore`: agregado `instance/`, `.DS_Store`, `*.db`. `instance/finance.db` (~8MB) y 3 `.DS_Store`
      ya estaban commiteados — se hizo `git rm --cached` (dejan de trackearse, siguen en el historial viejo).

### 0.2 Seguridad y configuración
- [x] `[S]` Quitar defaults `'xxx'` de SECRET_KEY/JWT_SECRET_KEY → `ProductionConfig` ya no tiene default;
      `create_app()` falla con `RuntimeError` explícito si faltan en `ENV=production`. Dev/testing mantienen
      defaults claramente marcados como inseguros.
- [x] `[S]` Quitar `app.config["DEBUG"] = True` global; ahora respeta el `DEBUG` de cada config por entorno.
- [x] `[S]` `.env.example` documentando todas las variables (ENV, HOST, PORT, DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY).

### 0.3 Limpieza Brasil
- [x] `[S]` Eliminar `src/utils/brfinance/` y `check_stocks_news.py` (CVM) — ambos ya estaban muertos/rotos.
- [x] `[S]` Quitar `cvm_code` de StockModel (migración Alembic `00202d658c38`).
- [x] `[S]` Archivar `TicketModel.csv` (tickers .SA) en `/scripts/legacy`.
- [x] `[M]` Renombrar dominio `TransactionModel` vs. inversiones: **investigado, no hay colisión real hoy** —
      el dominio de inversión ya usa `OrderModel`/`orders`, no `TransactionModel`. Queda como decisión de
      naming a futuro, no como bug a corregir.

### 0.4 Calidad
- [x] `[M]` Pytest + fixtures con app factory y SQLite en memoria (`tests/conftest.py`); smoke tests de auth,
      home, blueprints registrados, y acceso anónimo/autenticado a las 5 rutas protegidas (`tests/`).
- [x] `[S]` GitHub Actions: lint (ruff) + tests en cada push (`.github/workflows/ci.yml`).
- [x] `[S]` Requirements ya estaban pinneados (`requirements.txt`); se agregó `requirements-dev.txt` +
      `pyproject.toml` con config de ruff (acotada a reglas de correctitud `E9,F` — el resto del codebase
      tiene deuda de estilo pre-existente fuera de alcance de este pase).

**Criterio de salida**: ✅ la app arranca con `create_app()` (`python app.py`), `pytest` en verde (15 passed,
1 xfail conocido), sin referencias a CVM/B3 en el flujo principal.

**Encontrado durante la ejecución, fuera del alcance original de Fase 0** (documentado, no resuelto salvo donde
se indica):
- `instance/finance.db` (el sqlite de dev) tiene mezcladas tablas de otro proyecto sin relación
  (`Permit`, `Ward`, `Street`, `Builder`, etc. — un esquema de permisos de construcción). No se tocaron esas
  tablas; vale la pena confirmar si ese archivo se está compartiendo entre proyectos por accidente.
- El historial de migraciones de Alembic nunca capturó la creación de `users`/`stocks`/`transactions`/`categories`
  (se crearon con `db.create_all()` en algún momento, no con una migración) — en una DB nueva `flask db upgrade`
  no las crea. No se reescribió el historial de migraciones; se trabajó sobre la DB de dev existente.
- `/stocks` sigue rota: el formulario `Stock` tiene campos `ticket/quantity/price/date` pero el template
  esperaba `form.stock` — bug pre-existente, cubierto por un test `xfail`. Como la Fase 1 reconstruye esta
  pantalla como screener real, no se intentó adivinar el fix correcto.
- `transactions_charts.py` tenía un bug real (500 para un usuario sin transacciones aún, `KeyError` de pandas
  en DataFrame vacío) — se corrigió con un guard mínimo al construir el DataFrame.
- `src/forms/StockForm.py` importaba mal (`from src.forms import StockForm` en vez de la clase `Stock`) —
  corregido, ya que bloqueaba directamente la verificación de esta fase.

---

## Fase 1 — Universo de acciones + fundamentales (2–3 semanas)

### 1.1 Modelo de datos
- [x] `[M]` Refactor `StockModel` → `Asset`:
      `symbol`, `yahoo_symbol` (AAPL vs RY.TO), `exchange` (TSX/TSXV/NYSE/NASDAQ), `currency` (CAD/USD),
      `name`, `sector`, `industry`, `country`, `website`, **`ir_website`**, `logo_url`, `is_active`.
      Índice único `(symbol, exchange)`.
- [x] `[M]` Nueva tabla `Fundamentals` (1-N con Asset, snapshot con `as_of_date`):
      `market_cap, pe, forward_pe, pb, ps, ev_ebitda, roe, roa, roic, gross_margin, operating_margin,
      net_margin, debt_to_equity, current_ratio, quick_ratio, dividend_yield, payout_ratio,
      dividend_rate, eps, eps_growth_5y, revenue_growth_5y, beta, fifty_two_week_high/low, price`.
      `roic` queda siempre `None` — yfinance no lo expone en `info`. `eps_growth_5y`/`revenue_growth_5y`
      se llenan con el YoY más cercano (`earningsGrowth`/`revenueGrowth`), no un CAGR real a 5 años.
- [x] `[S]` Tabla `DividendHistory` (asset_id, ex_date, pay_date, amount, currency).
- [x] `[S]` Migraciones Alembic para todo lo anterior. **No autogenerada**: `flask db migrate` choca
      con el mismo hallazgo de Fase 0 (`Permit.ward_id → Ward` inexistente en esta DB de dev) —
      migración escrita a mano (`migrations/versions/a1f42e9c8b3d_.py`). Aplicada y verificada contra
      la DB de dev real (backup previo en session scratchpad).
      **Decisión de producto durante la ejecución**: la DB de dev tenía 424 `stocks` heredadas de
      Brasil (.SA) con 1098 `orders`/13 `portfolios` dependientes. Manuel eligió **mantenerlas** en
      vez de borrarlas — se migraron con placeholders (`exchange='BR'`, `currency='BRL'`,
      `yahoo_symbol=symbol`, `name` desde `long_name`) en vez de fabricar datos CA/US falsos. Van a
      aparecer en el screener como 424 filas no-CA/US reales; no se cuentan para el criterio de
      salida de abajo.

### 1.2 Capa de proveedores de datos
- [x] `[L]` `src/services/market_data/` con interfaz `MarketDataProvider`
      (`get_profile`, `get_quote`, `get_fundamentals`, `get_dividends`) y primera implementación
      `YahooProvider` (yfinance). Retries/backoff centralizados, rate-limit configurable
      (`min_interval_seconds`). Tests con `yfinance.Ticker` mockeado (ver hallazgo de red abajo).
- [x] `[S]` Config `MARKET_DATA_PROVIDER=yahoo` (documentado en `.env.example`) para swap futuro.

### 1.3 Seed del universo CA/US
- [x] `[M]` Script `scripts/seed_universe.py`: **fuente cambiada** de TMX/NASDAQ100 (no se encontró
      CSV público confiable para ninguna de las dos en esta sesión) a **Wikipedia**: S&P/TSX Composite
      (CA) + S&P 500 (US), ambas verificadas accesibles y parseadas en vivo. Corrida real: **219 CA +
      503 US = 722 empresas reales sembradas**. Símbolo Yahoo normalizado (`.TO` para CA, `.`→`-` para
      US tipo BRK.B→BRK-B). Idempotente (upsert por symbol+exchange).
- [x] `[M]` Enriquecimiento (`YahooProvider.get_profile`) implementado, resumible (reintenta solo
      assets sin `website` aún) y tolerante a fallos — verificado correcto en un smoke test real, pero
      **Yahoo devuelve 429 de forma consistente desde la IP de salida de este sandbox** (confirmado con
      `curl` y con `yfinance` real contra varios símbolos), así que el enriquecimiento no completó en
      esta sesión. El mecanismo queda listo para correr desde un entorno sin ese rate-limit.
- [x] `[M]` Campo `ir_website`: heurística implementada (website + `/investors`|`/investor-relations`
      + `HEAD` best-effort). No verificable en esta sesión — depende de que `website` se haya llenado
      vía enriquecimiento, bloqueado por el mismo 429.

### 1.4 Jobs de actualización
- [x] `[M]` Job diario `refresh_fundamentals` (cron 18:00 `America/Toronto`, maneja DST correctamente
      a diferencia de un offset UTC fijo) — snapshot en `Fundamentals` por asset activo.
- [x] `[S]` Job cada 15 min `refresh_quotes` (solo precio) — solo para `asset_id` presentes en
      `OrderModel` (ya funciona hoy, no depende del rediseño de `Order` de Fase 3).
- [x] `[S]` Job diario FX `refresh_fx` (cron 18:30 ET) — Banco de Canadá Valet API, **respuesta real
      verificada en vivo** (`{"observations":[{"d":"...","FXUSDCAD":{"v":"..."}}]}`) → tabla `FxRate`.
- [x] `[S]` Tabla `JobRun` (job, started_at, finished_at, status, items_processed, **+ `error`** para
      que un fallo sea diagnosticable, no solo "failed"). Los 3 jobs quedan registrados en el scheduler
      (mismo patrón/guard que el job viejo, fuera de `app.testing`) — verificado que arrancan
      correctamente; no se esperó a una ejecución real por cron dentro de esta sesión.

### 1.5 Screener (pantalla "Acciones")
- [x] `[L]` Ruta `/stocks` reescrita por completo (reemplaza el form roto `form.stock`, ya cubierto
      antes por un test `xfail` que ahora pasa de verdad): tabla server-rendered con HTMX — columnas
      symbol+nombre, exchange, sector, precio, P/E, P/B, ROE, D/E, DY, payout, margen neto, market cap.
      Orden por columna, paginación, filtros (exchange, sector, rango por cada indicador — sidebar
      generada desde la misma lista que valida el backend, no puede desincronizarse), búsqueda por
      nombre/símbolo. Nulos (fundamentals aún no calculados) muestran "—", no "0.00" ni un crash.
- [x] `[S]` Export CSV del screener filtrado (`/stocks/export.csv`, misma lógica de filtros/orden).

**Desviación del plan original descubierta en ejecución**: `src/forms/StockForm.py` iba a eliminarse
(la asunción era que solo la alimentaba el `/stocks` roto) — **se mantuvo**, porque `/portfolio` la usa
de verdad para el modal "Nueva operación" (`ticket`/`quantity`/`price`/`date`). Borrarla hubiera roto
`/portfolio`.

**Hallazgo, no corregido (pre-existente, no introducido en esta fase)**: 486 de las 1098 `orders`
heredadas tienen `asset_id` (antes `stock_id`) con un símbolo de texto en vez de un id válido — bug
pre-existente en `OrdersFactory.check_stock_exists`, que al no encontrar el stock devuelve el símbolo
crudo como fallback. Confirmado idéntico antes y después de la migración (no es una regresión). Se
deja documentado; el importador B3 completo se reemplaza en Fase 3.

**Criterio de salida**: ⚠️ parcial — screener navegable y funcional con datos reales (722 empresas
CA+US reales de Wikipedia, sort/filtros/paginación/CSV todos verificados), pero **no llega a las
"≥500 empresas CA"** originales (TSX Composite son ~220; el universo TSXV completo no tiene fuente
gratuita confirmada) y **los fundamentales no están poblados** (bloqueado por el 429 de Yahoo desde
este sandbox, no por un bug — mecanismo verificado correcto). Pendiente para cerrar el criterio al
100%: (a) correr `python scripts/seed_universe.py` (sin `--limit`) desde una máquina sin ese
rate-limit para completar el enriquecimiento, (b) decidir una fuente real para TSXV, (c) opcional:
separar NYSE de NASDAQ para las 503 US (hoy `exchange='US'` genérico — la tabla de Wikipedia usada no
distingue) y sembrar Nasdaq-100 (su página de Wikipedia ya no incluye la tabla de componentes).

---

## Fase 2 — Página de empresa (1–2 semanas)

- [x] `[L]` Ruta `/stocks/<exchange>/<symbol>`:
      - Header: logo, nombre, symbol, exchange, sector, precio + variación día, botón "IR site" y "Website".
      - Grid de indicadores (los de Fundamentals) agrupados: Valuación / Rentabilidad / Endeudamiento / Dividendos.
      - Gráfico de precio histórico (1M/6M/1Y/5Y) — endpoint JSON + Chart.js.
      - Historial de dividendos (tabla + gráfico anual).
      - Descripción de la empresa (longBusinessSummary de yfinance).
- [x] `[M]` Endpoint `/api/assets/<id>/prices?range=` con caching (tabla `PriceHistory` EOD o fetch on-demand con cache).
      **Decisión**: fetch on-demand vía `YahooProvider.get_price_history` (yfinance `.history(period=...)`),
      con caché en memoria a nivel de módulo (`_price_history_cache`, TTL 15 min, keyed por
      `(yahoo_symbol, period)`) en vez de una tabla `PriceHistory` — evita el costo de un backfill/job
      diario para este pase y sirve datos "stale" si Yahoo falla en un refetch. Se puede migrar a tabla
      EOD más adelante si el volumen de tráfico lo justifica.
- [x] `[S]` Botón "Agregar a portafolio" → modal de nueva orden pre-llenado (mismo `StockForm`/endpoint
      stub `/api/stock` que usa el modal "Nueva orden" de `/portfolio`; la creación real de órdenes se
      aborda en Fase 3).
- [x] `[S]` SEO/UX: breadcrumbs (Acciones / exchange / symbol), estados de carga y empty states para el
      gráfico de precio (fetch vía JS, no HTMX — el endpoint devuelve JSON, no HTML parcial) y para
      dividendos/fundamentales sin datos aún.

**Hallazgo/decisión durante la ejecución**: el precio + variación día usa una cotización en vivo
(`provider.get_quote`) con `max_retries=1`/sin backoff (vs. el `YahooProvider` por defecto de los jobs,
que reintenta 3x con sleep) para no bloquear la carga de la página si Yahoo está rate-limitando desde
este sandbox; si la cotización en vivo falla, cae al último precio guardado en `Fundamentals`. Se agregó
columna `description` a `Asset` (migración `1779d5844790`) para persistir el `longBusinessSummary`,
poblada por el mismo paso de enriquecimiento de `seed_universe.py`.

**Criterio de salida**: ✅ cualquier empresa del universo tiene página completa (probado end-to-end con
datos reales de Yahoo vía AAPL — precio histórico, fundamentales, header — y con fixtures en los tests
automatizados para los casos sin datos).

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

## Fase 4a — Proventos, calendario y hechos relevantes oficiales (1–2 semanas)

> Split de la Fase 4 original (decisión 2026-08-20): se separa la parte de datos oficiales/estructurados
> (dividendos propios, filings regulatorios, earnings) de la parte de noticias de terceros (Fase 4b),
> porque tienen fuentes, formato de dato y criterio de salida distintos.

- [x] `[M]` `/dividends` (Proventos): recibidos por mes (gráfico barras), YoC por posición,
      proyección próximos 12 meses, calendario de ex-dates y pay-dates de las posiciones.
      **Agregado durante la ejecución**: nada poblaba `DividendHistory` (el provider tenía
      `get_dividends()` pero ningún job lo llamaba), así que se sumó el job `refresh_dividends`
      (solo assets con órdenes, no las 722 del universo). También se agregó UI de confirmar/descartar
      las `DividendReceived` sugeridas (columna nueva `dismissed`) — sin eso, `confirmed` no tenía
      forma de volverse `True` y la pantalla quedaba llena de estimados permanentes.
- [x] `[L]` Hechos relevantes regulatorios:
      - US: job `refresh_company_events` consulta **SEC EDGAR** (API pública JSON) para 8-K/10-Q/10-K
        de assets en portafolio → tabla `CompanyEvent` (`source=EDGAR`). CIK resuelto desde el mapa
        público ticker→CIK de SEC y persistido en `Asset.cik` (solo para US en cartera).
      - Canadá: **SEDAR+ no tiene API pública** → link directo a la búsqueda SEDAR+ en la página de
        empresa (sin ingestión estructurada); evaluar proveedor pago (QuoteMedia) si se vuelve crítico.
- [x] `[S]` Calendario de earnings (yfinance `.calendar`, nuevo método `get_calendar` en el provider)
      en página de empresa y en inbox — persistido como `CompanyEvent(kind=EARNINGS)`, una fila por
      asset actualizada in situ (la fecha estimada se mueve; una fila por corrida acumularía basura).
- [x] `[M]` `/inbox`: timeline de eventos de las empresas del portafolio (dividendo anunciado, filing
      EDGAR, earnings) con marcado leído/no leído (`CompanyEventRead`, presencia = leído) y badge de
      no leídos en el nav. Se extiende en Fase 4b para incluir noticias.

**Criterio de salida**: ✅ verificado contra la DB de dev real (Yahoo ya no rate-limitea desde este
entorno, a diferencia de Fases 1–3): `refresh_dividends` trajo **1498 dividendos históricos reales**
de los 37 assets en cartera + 3 ex-dates futuras, `refresh_company_events` escribió 10 earnings, y
EDGAR en vivo devolvió **15 filings reales de AAPL** (10-Q/8-K con links a sec.gov). `/dividends`
genera 479 sugerencias, infiere frecuencia (Mensual/Trimestral) y `/inbox` lista 13 eventos con
filtros y leído/no leído.

**Hallazgo durante la ejecución**: la cartera de dev es casi toda BRL legacy y **no hay `FxRate`
BRL→CAD**, así que todos los importes en CAD dan 0. Se agregó un banner de advertencia (mismo patrón
que `PortfolioService.warnings` en `/portfolio`) en vez de mostrar `C$0,00` silenciosamente. Para ver
números reales hace falta o una fuente de FX BRL→CAD o una cartera CA/US.

---

## Fase 4b — Noticias (Reuters, Yahoo, Google News, etc.) (1 semana)

> Segunda mitad del split de la Fase 4 original. Depende de `CompanyEvent` (creada en 4a) — agrega
> eventos `kind=NEWS` con `source` distinguiendo el proveedor.

- [x] `[M]` Capa de proveedores de noticias (`src/services/news/`, mismo patrón Strategy que
      `MarketDataProvider`): `YahooNewsProvider` (yfinance `.news`) y `GoogleNewsProvider`
      (RSS público `news.google.com/rss/search?q=...`, sin API key, locale `es-419/CA` para que los
      titulares vengan en el idioma de la UI). **Reuters queda fuera**: no tiene API ni RSS público
      gratuito por empresa. A diferencia de `get_provider()`, la factory `get_news_providers()`
      devuelve una **lista** — las noticias se agregan de todas las fuentes a la vez, no se
      intercambian (config `NEWS_PROVIDERS=yahoo,google`).
- [x] `[S]` Job `refresh_news` (interval 6h — las noticias salen durante el día, a diferencia de los
      jobs de cierre) sobre assets en cartera → `CompanyEvent` (`kind=NEWS`, `source=YAHOO|GOOGLE`).
      **Dedupe doble**: por hash de URL dentro de cada fuente, y por título normalizado entre fuentes
      en una ventana de 14 días — Yahoo y Google publican la misma nota con URLs distintas, así que
      dedupe solo por URL no alcanzaba.
- [x] `[S]` Feed de noticias en la página de empresa (sección propia, separada de "Hechos relevantes").
- [x] `[S]` `/inbox` ya soportaba el filtro "Noticias" desde 4a; se ajustó el render para que la
      headline sea el cuerpo del evento (no el resumen) y el link diga "Leer ↗" en vez de
      "Ver en EDGAR ↗" según `source`.

**Criterio de salida**: ✅ verificado en vivo contra la DB de dev — ambas fuentes responden desde
este entorno y las noticias reales aparecen en la página de empresa y en el inbox (138 noticias de
los 37 assets en cartera, 71 de Yahoo + 67 de Google).

**Ajuste posterior (mismo día): backfill on-demand para todo el universo.** Los 3 jobs solo barren
assets en cartera (37 de 1159), así que las demás empresas del screener mostraban dividendos,
noticias y hechos relevantes vacíos. Se agregó `src/services/company_data.py` — toda la ingesta
(dividendos, calendario, filings, noticias) vive ahí y la usan **tanto los jobs como la página de
empresa**, que rellena un asset la primera vez que alguien lo abre (caché de intentos de 6h, retries
acotados como la cotización en vivo, y nunca rompe la página si una fuente falla). Los jobs quedaron
finos y se dividieron por fuente: `refresh_dividends` (todo lo de Yahoo: histórico + ex-date + fecha
de resultados), `refresh_filings` (solo EDGAR, renombrado desde `refresh_company_events`) y
`refresh_news`. Verificado en vivo: AAPL/BCE/VALE3 se llenan en 1,7–2,5s la primera vez y 0,2s
después. **El guard inicial (`has_any_data`) tenía un bug**: un asset a medias — AAPL tenía filings
pero no dividendos ni noticias — contaba como "ya tiene datos" y no se completaba nunca; se
reemplazó por `needs_backfill()`, que mira dividendos y noticias por separado.

**Hallazgo durante la ejecución — el feed por ticker de Yahoo trae ruido**: pedirle noticias de `RY`
devuelve notas de *Rayonier (RYN)*, *Citizens & Northern (CZNC)* y ETFs genéricos; Google mete
páginas de referencia de bonos. yfinance no expone tickers relacionados por nota (ni `.news` ni
`yf.Search`), así que se agregó un **filtro de relevancia en el job** (`_is_about_asset`): se guarda
la nota solo si el símbolo aparece como token suelto, o el nombre de la empresa aparece, en el
titular o el resumen. En la corrida real descartó **106 de 244** notas (43%). Compromiso conocido:
puede descartar alguna nota legítima que no nombre a la empresa en el titular ni el resumen.

---

## Fase 5 — Insights y calificación (continuo)

- [x] `[M]` Semáforos por indicador: 19 reglas declarativas en `src/services/insights.py`, con
      medianas calculadas sobre el último snapshot de cada empresa (mínimo 3 comparables), fallback general
      y overrides explícitos para Financial Services, Real Estate, Utilities y Technology. Las empresas con
      múltiplos no comparables o datos ausentes quedan "Sin datos", no verdes ni en cero.
- [x] `[L]` Score de calidad 0–100 por empresa, calculado on-demand desde el último `Fundamentals`:
      valuación 25%, rentabilidad 30%, solidez 25%, dividendos 20%. La página de empresa muestra score total,
      cobertura, score/peso/indicadores disponibles y explicación favorable/neutral/atención por componente;
      los datos ausentes se excluyen y la cobertura hace visible la incertidumbre. No se persiste para evitar
      que quede desincronizado del snapshot que lo origina.
- [x] `[M]` Rankings: nueva pantalla `/tools/rankings`, accesible desde el perfil, con top dividend
      yield TSX, aristócratas canadienses y top ROE por sector. Aristócratas exige cinco aumentos
      interanuales consecutivos (seis totales anuales) y excluye el año calendario incompleto.
- [x] `[M]` Comparador de 2–4 empresas lado a lado en `/tools/comparator`, accesible desde el perfil:
      selección siempre explícita (nunca elige empresas por el usuario), columnas independientes con 27
      indicadores agrupados, ranking global, medallas por indicador, semáforos y score; autocomplete y ranura
      visible para agregar/quitar activos. Desde cada página de empresa, el botón "Comparar" abre la herramienta
      con ese activo preseleccionado y lista para sumar otro. Incluye gráfico de rentabilidad normalizada
      1M/6M/1A/5A y calculadora de una inversión hipotética, usando series reales del proveedor configurado.
- [ ] `[M]` Alertas por email: precio objetivo, ex-date próxima, nuevo filing.
- [ ] `[L]` (Opcional) Migrar proveedor a EODHD/FMP cuando yfinance quede corto.

---

## Fase 6 — Comunidad de inversores (2–3 semanas)

> Referencias: pestaña "Comunidade" de meusdividendos — feed continuo de análisis, dudas y
> lecturas de mercado entre inversores. esta tambien es otra referencia: https://investidor10.com.br/comunidade/

- [x] `[M]` Modelos: `Post` (user, title, body, category, created_at), `Comment`,
      `Vote` (up/down por user+post), `PostTickerMention` (N-N post↔asset). Se sumaron
      `PostReport` (moderación) y `users.is_admin`. Post y Comment usan soft-delete
      (`is_deleted`/`deleted_by_id`) para que votos, comentarios y menciones queden íntegros.
- [x] `[M]` Parser de menciones `$RY`, `$ENB` → chips clickeables que llevan a la
      página de la empresa; alimenta "Activos en destaque". Lee **título y cuerpo** (un ticker
      en el titular también es una mención), pero solo enlaza dentro del cuerpo: el título ya
      es un enlace al post y los `<a>` no anidan. Un símbolo ambiguo resuelve al listado
      canadiense primero (TSX → TSXV → US); uno inexistente queda como texto plano.
- [x] `[L]` `/community`: feed con tabs **Recientes / Más votados / En alta**, categorías
      (Feed, Análisis, Dudas, Dividendos, Noticias, Operaciones, Sugerencias), composer
      ("Comparte un análisis, noticia o duda…"), votos ↑↓ y contador de comentarios (HTMX).
      "En alta" ordena por votos + comentarios dentro de una ventana de 7 días. Votar dos
      veces igual retira el voto; votar al revés lo invierte.
- [x] `[M]` Sidebar: "Recientes" (últimas noticias de dividendos del universo, sin filtrar por
      portafolio) y "Activos en destaque" (ranking de menciones últimos 7 días).
- [x] `[M]` Página de post con hilo de comentarios; editar/borrar propio contenido. Un admin
      puede eliminar contenido ajeno pero nunca reescribirlo.
- [x] `[S]` Feed por empresa: sección "Comunidad" dentro de la página de empresa filtrando
      posts que mencionan su ticker, cargada por HTMX después del pintado.
- [x] `[S]` Moderación mínima: reporte de post, soft-delete por admin, rate-limit de publicación
      (5 posts y 20 comentarios por hora, ventana móvil).
- [x] `[S]` Barra superior de mercado (market strip) en toda la app: TSX Composite, S&P 500,
      NASDAQ, USD/CAD, tasa BoC (Valet V39079), estado del mercado con feriados del TSX
      — job cada 15 min. Cada fuente está aislada: una caída de Yahoo no borra la tasa BoC.

---

## Fase 7 — Estadísticas agregadas de portafolios (3–4 semanas, cuando haya masa crítica)

> Objetivo: transformar las posiciones derivadas de las órdenes en estadísticas anónimas de mercado
> interno: activos más presentes, combinaciones frecuentes y arquetipos de portafolio. Las órdenes
> siguen siendo la única fuente de verdad; toda tabla de esta fase es una proyección analítica
> regenerable y nunca se edita manualmente.
>
> **Condición para iniciar**: Postgres en producción, aislamiento multiusuario de órdenes/cuentas
> cubierto por tests, precios y FX diarios confiables, y suficientes portafolios no vacíos para formar
> cohortes de al menos 10 usuarios. Como referencia operativa, evaluar la fase a partir de ~100 usuarios
> con portafolio activo; el umbral final debe configurarse según la distribución real y no quedar fijo
> en el código.

### 7.1 Definición de población y métricas
- [ ] `[M]` Definir **usuario elegible** para cada fecha: usuario con al menos una posición neta positiva,
      excluyendo cuentas de prueba, administradores técnicos y datos importados incompletos. Documentar
      zona horaria, fecha de corte y tratamiento de órdenes corregidas o cargadas retroactivamente.
- [ ] `[S]` Definir **tenedor de un activo** como un usuario distinto cuya cantidad consolidada del activo
      sea mayor que cero al cierre de la fecha. Varias cuentas del mismo usuario cuentan una sola vez.
- [ ] `[S]` Definir **penetración** como `usuarios que poseen el activo / usuarios elegibles`, mostrando
      ambos valores y la fecha del snapshot. Nunca usar número de compras como sustituto de usuarios.
- [ ] `[M]` Para cada activo calcular: usuarios tenedores, penetración, valor agregado en CAD, peso medio,
      **peso mediano**, percentiles 25/75, posición mediana dentro de la cartera y variación de tenedores
      frente a 7, 30 y 90 días. La mediana será la medida principal para evitar que carteras grandes
      distorsionen el resultado.
- [ ] `[S]` Mantener separada la métrica de **actividad de trading**: compradores, vendedores y órdenes
      netas por período. No mezclar “más operado” con “más poseído”.
- [ ] `[M]` Calcular estadísticas de composición: número mediano de posiciones, peso mediano del top 1 y
      top 5, concentración, distribución por sector/país/moneda/clase de activo y porcentaje de carteras
      con exposición internacional.

### 7.2 Proyección analítica y jobs
- [ ] `[L]` Crear `UserPositionSnapshot`, una proyección diaria reconstruible con:
      `date`, `user_id`, `asset_id`, `quantity`, `market_value_cad`, `portfolio_value_cad`,
      `portfolio_weight_percent` y versión del algoritmo. Restricción única
      `(date, user_id, asset_id)` e índices por `(date, asset_id)` y `(user_id, date)`.
- [ ] `[M]` Job diario idempotente, posterior a precios y FX, que recalcule posiciones desde `Order`,
      consolide todas las cuentas del usuario por activo y escriba el snapshot de la fecha. Debe poder
      reprocesar un rango completo cuando cambie una orden histórica o el algoritmo de costo/FX.
- [ ] `[M]` Crear agregados diarios regenerables —vista materializada o tablas de caché— para popularidad
      de activos, pares/tríos frecuentes y patrones de cartera. La UI nunca consultará todas las órdenes
      de todos los usuarios durante una request.
- [ ] `[S]` Registrar cada corrida en `PortfolioAnalyticsRun`: inicio/fin, fecha calculada, versión,
      usuarios elegibles, filas producidas, cohortes suprimidas y error. Alertar si cae bruscamente la
      población o el valor agregado respecto del día anterior.
- [ ] `[M]` Reconciliación automática: para una muestra de usuarios, la suma de posiciones del snapshot
      debe coincidir con `PortfolioService`; los conteos agregados deben coincidir con los snapshots
      subyacentes antes de publicar una fecha.

### 7.3 Activos y combinaciones más frecuentes
- [ ] `[M]` Ranking **Activos más presentes** con símbolo, empresa, usuarios tenedores, penetración,
      peso mediano, rango intercuartil y cambio 30 días. Filtros por fecha, exchange, sector, país y
      clase de activo; orden por tenedores, penetración o peso mediano.
- [ ] `[M]` Ranking de **pares y tríos más frecuentes** entre posiciones actuales. Mostrar soporte
      absoluto, porcentaje de portafolios y pesos medianos de los componentes; no generar combinaciones
      que no alcancen el umbral de privacidad.
- [ ] `[M]` Métrica “Quienes tienen X también suelen tener…” basada en probabilidad condicional y
      acompañada por soporte y *lift*. El soporte evita recomendaciones engañosas producidas por muestras
      pequeñas y el *lift* distingue afinidad real de activos que simplemente son populares en general.
- [ ] `[S]` Enlazar cada símbolo a su página de empresa y permitir descargar únicamente resultados
      agregados en CSV, respetando exactamente los mismos filtros y reglas de supresión de la pantalla.

### 7.4 Portafolios repetidos y similares
- [ ] `[M]` Implementar una **firma exacta por conjunto**: lista ordenada de `asset_id` con posición
      positiva, sin cantidades. Permite contar cuántos usuarios poseen exactamente la misma combinación;
      separar por número de posiciones para que carteras pequeñas no dominen todo el ranking.
- [ ] `[M]` Implementar una **firma aproximada por composición** usando los principales activos y pesos
      redondeados a bandas configurables (inicialmente 5 puntos porcentuales). Mostrar siempre que los
      pesos son rangos, no composiciones individuales exactas.
- [ ] `[L]` Agrupar portafolios similares mediante vectores de pesos: similitud Jaccard para activos
      compartidos y similitud coseno para composición. Versionar parámetros, elegir el número de grupos
      con métricas reproducibles y asignar nombres descriptivos después de revisar sus componentes
      dominantes, por ejemplo “ETF global pasivo” o “Dividendos canadienses”.
- [ ] `[M]` Para cada arquetipo mostrar: cantidad y porcentaje de usuarios, activos/sectores dominantes,
      número mediano de posiciones, concentración top 5, exposición geográfica y rango de pesos. No
      mostrar una cartera individual representativa ni permitir reconstruir la de un usuario.
- [ ] `[M]` Medir estabilidad de los grupos entre corridas. Si un cambio de parámetros altera
      sustancialmente los arquetipos, mantener la versión anterior visible hasta validar la nueva y
      explicar la ruptura de serie histórica.

### 7.5 Pantalla `/statistics`
- [ ] `[L]` Crear página server-rendered + HTMX con cuatro vistas:
      **Resumen**, **Activos populares**, **Combinaciones** y **Portafolios similares**.
- [ ] `[M]` Resumen con KPIs: usuarios elegibles, posiciones por cartera, concentración top 5,
      activo con mayor penetración, sector dominante y fecha/estado del último cálculo. Incluir evolución
      de 30/90 días sin presentar el cambio como dato en tiempo real.
- [ ] `[M]` Activos populares: tabla ordenable y buscable, evolución de tenedores, distribución de peso
      y filtros compartibles en la URL. Diferenciar visualmente “más poseído”, “mayor peso” y “más operado”.
- [ ] `[M]` Combinaciones: pares/tríos, co-tenencia condicionada y carteras exactas frecuentes, con una
      explicación legible de soporte, penetración y *lift* para evitar interpretaciones incorrectas.
- [ ] `[L]` Portafolios similares: tarjetas de arquetipos con composición agregada por activos y sectores,
      rangos de concentración y evolución del tamaño del grupo. Presentarlos como descripción estadística,
      nunca como recomendación de inversión ni señal automática para copiar operaciones.
- [ ] `[S]` Estados de carga, fecha del último snapshot, metodología enlazada, empty state cuando no haya
      masa crítica y banner de datos parciales si fallaron precios/FX o la corrida no pasó reconciliación.
- [ ] `[S]` Responsive y accesible: tablas utilizables con teclado, gráficos con alternativa textual,
      colores no usados como único indicador y números con formato CAD/porcentaje coherente con el resto.

### 7.6 Privacidad, consentimiento y seguridad
- [ ] `[M]` Aplicar **k-anonimato mínimo configurable**, inicialmente `k=10`: ocultar cualquier activo,
      combinación, filtro o arquetipo con menos de 10 usuarios. La supresión se aplica en backend y en
      exports, no solo ocultando elementos en HTML.
- [ ] `[M]` Revisar filtros combinables para evitar ataques de diferenciación: bloquear cortes demasiado
      estrechos, no exponer conteos casi idénticos entre fechas y redondear conteos/rangos cuando sea
      necesario. No exponer `user_id`, cantidades, costos, brokers ni valores de carteras individuales.
- [ ] `[M]` Añadir preferencia de participación/opt-out para analítica comunitaria y excluir al usuario
      de snapshots futuros según la política de producto. Documentar retención y cómo regenerar agregados
      si alguien retira el consentimiento.
- [ ] `[S]` Página de metodología: definiciones, universo incluido, fecha de corte, tamaño mínimo de
      muestra, tratamiento de cuentas múltiples y disclaimer de que popularidad no equivale a calidad
      ni constituye asesoramiento financiero.
- [ ] `[M]` Test específico de aislamiento: ningún endpoint o export debe devolver posiciones de un
      usuario, aceptar un `user_id` arbitrario ni permitir inferir una cartera mediante filtros sucesivos.

### 7.7 Calidad, rendimiento y lanzamiento
- [ ] `[M]` Tests unitarios de cantidades netas, consolidación multi-cuenta, penetración, percentiles,
      firmas, soporte/*lift*, similitud y supresión `k`; fixtures con órdenes corregidas, ventas totales,
      activos sin precio y FX faltante.
- [ ] `[M]` Tests de integración del pipeline completo `Order → UserPositionSnapshot → agregados → UI`,
      incluyendo rerun idempotente, backfill y cambio de versión del algoritmo.
- [ ] `[S]` Presupuesto de rendimiento: la página debe leer solo agregados indexados; fijar objetivo de
      respuesta p95 y medir duración/memoria del job con el volumen real antes del lanzamiento.
- [ ] `[S]` Activación mediante feature flag: primero solo administración, después beta opt-in y finalmente
      disponibilidad general cuando privacidad, reconciliación y estabilidad de datos estén validadas.
- [ ] `[M]` Instrumentación de uso sin registrar portafolios individuales: vistas por sección, filtros
      usados, exports y errores del pipeline. Revisión periódica para retirar métricas confusas o sin uso.

**Criterio de salida**: con una cohorte que supere el mínimo de privacidad, `/statistics` muestra activos,
combinaciones y arquetipos reproducibles desde snapshots diarios; todos los conteos pasan reconciliación,
ningún resultado contiene menos de `k` usuarios ni revela datos individuales, el pipeline puede reconstruirse
desde órdenes y la pantalla explica fecha, muestra y metodología de cada métrica.

---

## Infraestructura transversal (cuando toque)
- [ ] `[S]` Migrar SQLite → Postgres (necesario antes de multiusuario real).
- [ ] `[M]` Deploy: Docker + gunicorn; jobs APScheduler en proceso worker separado (no dentro del web worker).
- [ ] `[S]` Backups de DB + monitoreo de jobs.

## Orden recomendado de ejecución
```
Fase 0 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 4a ──► Fase 4b ──► Fase 5 ──► Fase 6 ──► Fase 7
(salud)   (datos)    (empresa)  (portafolio) (proventos+  (noticias) (insights) (comunidad) (estadísticas)
                                              regulatorio)
```
La comunidad va al final: necesita usuarios activos y páginas de empresa a las cuales enlazar
las menciones; puede adelantarse si el objetivo es validar interés temprano.
La Fase 1 va antes que el portafolio v2 porque el catálogo de assets con símbolos normalizados
es prerequisito de las órdenes multi-exchange.
La Fase 7 se planifica después de la comunidad, pero su verdadero disparador es la masa crítica:
Postgres, snapshots diarios confiables y cohortes suficientemente grandes para publicar estadísticas
sin comprometer privacidad. Puede desarrollarse técnicamente antes y mantenerse detrás de un feature flag.
