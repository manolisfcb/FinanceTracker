# .claude — Plan y Diseño del Proyecto

Documentación de la evolución de FinanceTracker hacia **TrueNorth Analytics**:
plataforma de portafolio + análisis fundamental para el mercado canadiense (TSX/TSXV) y
acciones US compradas desde Canadá. Referencias: meusdividendos.com, Smartfolio, Suno Analítica.

## Estructura

| Carpeta | Contenido |
|---|---|
| [analisis/](analisis/) | `01-estado-actual.md` — auditoría del código actual: qué existe, bugs, qué se aprovecha, fuentes de datos investigadas para Canadá |
| [plano/](plano/) | `00-vision.md` (visión y fases) · `01-plan-detallado.md` (tareas por fase con estimaciones) · `02-modelo-datos.md` (ER diagram objetivo) |
| [disenho/](disenho/) | Mockups de las 7 pantallas (`*.dc.html` + `canvas.json`) y el canvas publicado `maplefolio-pantallas.html` |

## Diseño

Canvas editable con las 7 pantallas (Dashboard, Portafolio, Screener, Empresa, Dividendos,
Inbox, Comunidad): https://claude.ai/code/artifact/c7b12c8e-f226-4a26-bae9-05ba29f183a4

Sistema visual: fondo claro cálido `#f7f6f3`, tipografía IBM Plex Sans + IBM Plex Mono
(números tabulares) + Instrument Serif (marca/títulos), acento rojo maple `#b3372b`,
verde `#1a7f4e` / rojo `#c23934` para P&L.

## Fases (resumen)

0. Saneamiento técnico (app factory, bugs, seguridad, limpieza de todo lo de Brasil)
1. Universo de acciones CA/US + fundamentales + screener
2. Página de empresa
3. Portafolio v2 (multi-moneda CAD/USD, cuentas TFSA/RRSP, import brokers canadienses)
4. Proventos + calendario + hechos relevantes (SEDAR+/EDGAR)
5. Insights: semáforos, scores, rankings, alertas
6. Comunidad de inversores (feed, votos, menciones $TICKER)
