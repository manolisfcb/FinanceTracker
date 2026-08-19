# Estado Actual del Proyecto — FinanceTracker

> Auditoría realizada el 2026-08-19. Objetivo: base para evolucionar hacia una plataforma
> tipo Meus Dividendos / Smartfolio / Suno Analítica, enfocada en el mercado **canadiense**
> (TSX/TSXV) + acciones **americanas** compradas desde Canadá.

## 1. Qué existe hoy

### Stack
| Capa | Tecnología |
|---|---|
| Backend | Flask 3.1 + Flask-RESTful + Flask-Login + Flask-JWT-Extended + Flask-Migrate (Alembic) |
| ORM / DB | SQLAlchemy 2.0 + SQLite (`instance/finance.db`) |
| Frontend | Jinja2 + Tailwind (CDN) + DaisyUI (CDN) + HTMX + Chart.js |
| Datos de mercado | `yfinance` (scraping de Yahoo Finance) |
| Jobs | Flask-APScheduler (`update_stocks_info` cada hora) |
| Datos regulatorios | `src/utils/brfinance/` — conector a la **CVM de Brasil** (no aplica a Canadá) |

### Modelos existentes (`src/models/`)
- **UserModel** — usuarios con login (username/email/password hasheado). ✅ Funcional.
- **StockModel** — catálogo de acciones: symbol, long/short name, website, sector, industry,
  country, `cvm_code` (Brasil), previous_close, dividend_yield, current_price, 52wk high.
  ⚠️ Orientado a B3/Brasil (`cvm_code`, símbolos `.SA`). Sin indicadores fundamentales (P/L, ROE, deuda…).
- **OrderModel** — órdenes BUY/SELL (user, stock, qty, price, date). ✅ Base sólida.
- **PortfolioModel** — posición consolidada (avg_price, cost, profit, % return, dividendos).
  ⚠️ Es una *tabla materializada* que se regenera con `to_sql(if_exists='append')` → duplica filas en cada import.
- **PortfolioSnapshotModel** — 🐛 tiene `db.ForeingKey` (typo) → **crashea al importar**. No está en `__init__.py`.
- **TransactionModel + Category** — finanzas personales (income/expense). Es otro dominio; convive con el de inversiones.

### Rutas / vistas (`src/routes/`)
- `/` (landing), `/register`, `/login`, `/logout` — auth funcional.
- `/dash` — dashboard con **datos mockeados** hardcodeados.
- `/portfolio` — lee de DB vía SQL crudo (`src/utils/querys.py`, ⚠️ f-string → inyección SQL) + gráficos mockeados.
- `/stocks` — lista órdenes; el POST usa campos que ya no existen en StockModel (roto).
- `/transactions`, `/transactions_charts` — gastos personales con filtros + HTMX.
- API REST: `/api/stock` (stub "hello world"), `/api/upload-portfolio` (import Excel **de B3 Brasil**).

### Pipeline de datos actual
- `TicketModel.csv` — 853 tickers **brasileños** (.SA) con sector/industry/website (via yfinance).
- Job cada hora: actualiza precio/previous_close/52wkHigh con yfinance por cada stock en DB.
- Import de portafolio: formato Excel de **B3** (columnas en portugués: "Data do Negócio", "Código de Negociação"…), estrategia por transacción o por posición (esta última incompleta — no retorna nada).

### Scripts sueltos en la raíz
`get_portfolio.py`, `get_stocks_info.py`, `generate_tickets.py`, `generate_transactions.py`,
`upload_orders.py`, `upload_current_portfolio.py`, `teste.py`, `teste.html`, `binance.ipynb`,
PDFs de la CVM. Son experimentos que hay que mover a `/scripts` o borrar.

## 2. Problemas técnicos (deuda a pagar antes de crecer)

1. **`app.py` monolítico sin app-factory real** — hay un `create_app()` pero no se usa; todo se hace
   a nivel de módulo con imports circulares (`from app import db` en modelos). Bloquea tests y despliegue.
2. **Bug fatal**: `PortfolioSnapshots.py` → `db.ForeingKey`.
3. **Inyección SQL** en `src/utils/querys.py` (f-string con `user_id`; usar parámetros bind).
4. **Import de portafolio duplica posiciones** (`if_exists='append'` sin limpiar las del usuario).
5. **Rutas sin `@login_required`** (`/portfolio`, `/dash`, `/stocks` lo tienen comentado) y
   `/portfolio` usa `current_user.id` → crash si no hay sesión.
6. **Todo acoplado a Brasil**: cvm_code, sufijo `.SA`, brfinance/CVM, formato B3, tickers en CSV.
7. **Dos dominios mezclados** (finanzas personales + inversiones) sin separación de blueprints/nombres.
8. **Sin tests, sin CI**, secrets con default `'xxx'`, `DEBUG=True` forzado en producción.
9. **yfinance como única fuente** — sin licencia, frágil (los retries del job ya lo evidencian), sin fundamentales completos ni datos de dividendos históricos confiables.
10. **UI inconsistente**: estilos inline en `base.html` + `styles.css` + Tailwind CDN + DaisyUI; textos mezclan inglés/español/portugués.

## 3. Qué se aprovecha para la nueva visión

✅ **Se queda (con refactor):**
- Auth completo (User/login/register).
- OrderModel — el corazón del portafolio (las posiciones se *derivan* de órdenes).
- Patrón Strategy de importadores (OrdersFactory/PortfolioFactory) → se adapta a brokers canadienses (Questrade, Wealthsimple, IBKR).
- APScheduler para jobs de actualización.
- HTMX + Tailwind como enfoque de frontend (sin SPA).

🔁 **Se transforma:**
- StockModel → catálogo multi-exchange (TSX/TSXV/NYSE/NASDAQ) + tabla separada de fundamentales.
- Job de yfinance → capa de proveedores de datos con adaptadores (yfinance para MVP, FMP/EODHD para producción).
- `TicketModel.csv` brasileño → seed del universo canadiense/US.

❌ **Se retira:**
- `brfinance`/CVM, cvm_code, formato B3, scripts de la raíz, PDFs, notebook de Binance.
- (Decisión pendiente) módulo de gastos personales: extraer a su propio blueprint o eliminarlo del alcance.

## 4. Referencias de producto (lo que queremos replicar)

- [meusdividendos.com](https://www.meusdividendos.com/) — comunidad + rankings de dividendos + fundamentales.
- [smartfolio.meusdividendos.com](https://smartfolio.meusdividendos.com/free/) — portafolio: carteira, proventos, transações, extrato, alocación con plan vs. real.
- [suno.com.br/analitica](https://www.suno.com.br/analitica/acoes/mbrf3/) — página por empresa: indicadores fundamentales, histórico, gráficos, hechos relevantes.

## 5. Fuentes de datos para Canadá (investigado 2026-08)

| Fuente | Uso | Notas |
|---|---|---|
| **yfinance** | MVP: precios + fundamentales básicos (trailingPE, ROE, debtToEquity, payout…) | Gratis, sin licencia formal, frágil. Suficiente para empezar. Tickers TSX = sufijo `.TO`, TSXV = `.V`. |
| **[EODHD](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds)** | Producción: fundamentales globales + EOD + dividendos históricos | Cubre TSX/TSXV/US en un solo plan. |
| **[Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs/tsx-prices-api)** | Alternativa: estados financieros estandarizados TSX + US | ~$22–59/mes. |
| **[SEDAR+](https://www.sedarplus.ca/home/)** | Hechos relevantes / filings canadienses | **Sin API pública** ([OSC](https://www.osc.ca/en/industry/sedarplus)); acceso vía scraping cuidadoso o proveedores (QuoteMedia). Equivalente a los "fatos relevantes" de la CVM. |
| **SEC EDGAR** | Filings de empresas US (8-K = hechos relevantes) | API pública gratuita y estable (full-text search + submissions JSON). |
| **Sitios IR de cada empresa** | Link directo "Investor Relations" por empresa | Se guarda como campo `ir_website` en el catálogo; seed manual/semiautomático. |
| **TMX / TSX listings** | Universo de tickers TSX/TSXV | Archivos de emisores listados de TMX Group para poblar el catálogo. |
