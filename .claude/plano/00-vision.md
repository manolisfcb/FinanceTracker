# Visión del Producto — TrueNorth Analytics

Plataforma unificada de inversiones para el inversor **canadiense**:

1. **Portafolio** — registrar compras/ventas de acciones canadienses (TSX/TSXV) y americanas
   (NYSE/NASDAQ) compradas desde Canadá; ver posición consolidada, rentabilidad, dividendos,
   alocación plan vs. real. Multi-moneda CAD/USD.
2. **Universo de acciones** — catálogo completo de empresas invertibles desde Canadá, cada una
   con su link de **Investor Relations**, exchange, sector, industria.
3. **Análisis fundamental** — screener con indicadores por empresa: P/E, P/B, ROE, ROA,
   deuda/patrimonio, márgenes, dividend yield, payout, crecimiento. Primero *mostrar*, después
   *calificar* (bueno/malo, semáforos, score).
4. **Hechos relevantes** — noticias y filings por empresa (SEDAR+ para Canadá, EDGAR 8-K para US),
   calendario de dividendos y resultados.
5. **Insights** — a futuro: alertas, rankings de dividendos, score de calidad, comparador.
6. **Estadísticas agregadas** — cuando exista masa crítica: activos más presentes, combinaciones
   frecuentes y arquetipos de portafolio, siempre anónimos y con umbral mínimo de privacidad.

## Principios
- **Órdenes como fuente de verdad**: las posiciones del portafolio se derivan siempre de las
  órdenes; nunca se editan a mano.
- **Datos con capa de proveedor intercambiable**: empezar gratis (yfinance), poder migrar a
  EODHD/FMP sin tocar el dominio.
- **Server-rendered + HTMX**: sin SPA; mantener el stack Flask/Jinja/Tailwind actual.
- **CAD como moneda base** con conversión FX diaria para activos en USD.

## Fases
| Fase | Entregable | Referencia |
|---|---|---|
| 0 | Saneamiento técnico (app factory, bugs, seguridad, limpieza Brasil) | — |
| 1 | Catálogo de acciones CA/US + fundamentales + screener | suno analítica (tabla) |
| 2 | Página de empresa (perfil, indicadores, gráficos, IR link) | suno analítica (detalle) |
| 3 | Portafolio v2 (multi-moneda, dividendos, snapshots, import brokers CA) | smartfolio |
| 4 | Proventos + calendario + hechos relevantes (SEDAR+/EDGAR) | meusdividendos |
| 5 | Insights: scores, semáforos, rankings, alertas | meusdividendos/suno |
| 6 | Comunidad de inversores (feed, votos, menciones $TICKER) | meusdividendos Comunidade |
| 7 | Estadísticas agregadas de activos y portafolios | Analítica interna anonimizada |
