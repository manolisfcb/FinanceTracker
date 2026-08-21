# TrueNorth — Roadmap futuro: “¿Dónde pongo mi próximo aporte?”

## Objetivo

Construir una feature determinística, explicable y configurable que ayude al usuario a decidir cómo distribuir un nuevo aporte entre los activos que ya posee, sin depender de LLMs.

La feature deberá combinar:

- valoración;
- dividendos;
- calidad financiera;
- peso actual en cartera;
- peso objetivo;
- reglas definidas por el usuario;
- score de oportunidad;
- optimización del nuevo aporte con OR-Tools;
- explicación clara de por qué un activo fue priorizado o descartado.

> Principio de producto: TrueNorth no debe “adivinar” qué comprar. Debe calcular, puntuar y optimizar según reglas transparentes.

---

# 1. Resultado esperado para el usuario

Ejemplo:

```text
Tengo C$1,000 para invertir

Best fit for your strategy
────────────────────────────────

1. FTS                       91/100
   ✓ Debajo del precio techo
   ✓ DY por encima de su media 5Y
   ✓ Dividendos creciendo
   ✓ Cartera subponderada

   Aporte sugerido
   C$480


2. TD                        84/100
   ✓ Debajo del precio techo
   ✓ DY atractivo históricamente
   ✓ Cartera subponderada

   Aporte sugerido
   C$390


3. RY                        71/100
   ~ Valoración neutral
   ~ Cerca de su peso objetivo

   Aporte sugerido
   C$130


ENB                           54/100

No priorizado
   ✕ Encima del precio techo
   ✕ Posición sobreponderada
```

---

# 2. Arquitectura conceptual

```text
Portfolio
   │
   ├── Positions
   ├── Average Cost
   ├── Current Allocation
   ├── Target Allocation
   └── Account Types
          │
          ▼
Market + Fundamental Data
          │
          ├── Price
          ├── Dividend Yield
          ├── Dividend History
          ├── Earnings
          ├── Debt
          ├── ROE / ROIC
          ├── Payout
          └── REIT Metrics
                 │
                 ▼
        Scoring Engine
                 │
        ┌────────┼─────────┐
        │        │         │
   Valuation  Quality   Portfolio Fit
        │        │         │
        └────────┼─────────┘
                 ▼
        Opportunity Score
                 │
                 ▼
      Optimization Engine
           OR-Tools
                 │
                 ▼
 Suggested Contribution
                 │
                 ▼
       Explanation Layer
```

---

# 3. Epics

## EPIC 1 — Modelo de estrategia de inversión

### Objetivo

Permitir que TrueNorth evalúe activos usando una estrategia explícita y reproducible.

### Tareas

- [ ] Crear entidad `InvestmentStrategy`.
- [ ] Permitir estrategias predefinidas.
- [ ] Crear estrategia `Bazin`.
- [ ] Crear estrategia `Dividend Growth`.
- [ ] Crear estrategia `Quality`.
- [ ] Crear estrategia `Balanced`.
- [ ] Permitir estrategia personalizada.
- [ ] Persistir pesos y thresholds por estrategia.
- [ ] Permitir activar/desactivar reglas individualmente.
- [ ] Versionar estrategias para mantener reproducibilidad histórica.

### Modelo sugerido

```python
InvestmentStrategy

id
user_id
name
strategy_type
valuation_weight
dividend_weight
quality_weight
portfolio_fit_weight
minimum_score
allow_above_price_ceiling
max_position_weight
created_at
updated_at
```

### Ejemplo de configuración

```json
{
  "name": "Bazin",
  "weights": {
    "valuation": 0.40,
    "dividend": 0.25,
    "quality": 0.25,
    "portfolio_fit": 0.10
  },
  "rules": {
    "minimum_dividend_yield": 0.03,
    "maximum_payout_ratio": 0.80,
    "maximum_position_weight": 0.15,
    "require_below_price_ceiling": true
  }
}
```

---

# 4. EPIC 2 — Precio Techo y Valuation Score

## 4.1 Precio Techo Bazin

Implementar:

```text
Precio Techo Bazin =
Promedio anual de dividendos por acción de los últimos 5 años
/
Yield mínimo objetivo
```

Valor clásico:

```text
Yield objetivo = 6%
```

### Tareas

- [ ] Calcular dividendos anuales por ticker.
- [ ] Calcular promedio de dividendos de los últimos 5 años.
- [ ] Ignorar o tratar separadamente dividendos extraordinarios.
- [ ] Permitir configurar el yield objetivo.
- [ ] Guardar `bazin_price_ceiling`.
- [ ] Guardar fecha de cálculo.
- [ ] Guardar datos utilizados para auditoría.
- [ ] Mostrar precio actual vs precio techo.
- [ ] Mostrar margen respecto al techo.

### Fórmula

```text
upside_to_ceiling =
(price_ceiling - current_price)
/
price_ceiling
```

---

## 4.2 Valuation Score

Crear un score de `0–100`.

Ejemplo inicial:

```text
20%+ debajo del techo     100
10–20% debajo              80
0–10% debajo               60
0–10% encima               30
>10% encima                 0
```

### Tareas

- [ ] Implementar `calculate_valuation_score()`.
- [ ] Parametrizar thresholds.
- [ ] Añadir unit tests.
- [ ] Guardar explicación del score.
- [ ] Permitir otros modelos de valoración en el futuro.

---

# 5. EPIC 3 — Dividend Score

## Objetivo

Evitar considerar un dividend yield alto como automáticamente positivo.

Comparar el yield actual contra la historia de la propia empresa.

### Métrica principal

```text
relative_yield =
current_dividend_yield
/
average_dividend_yield_5y
```

### Ejemplo de scoring

```text
>= 1.25        100
>= 1.10         80
0.90–1.10       60
0.75–0.90       30
< 0.75          10
```

### Tareas

- [ ] Obtener dividend yield actual.
- [ ] Calcular dividend yield histórico.
- [ ] Calcular promedio 3Y.
- [ ] Calcular promedio 5Y.
- [ ] Calcular crecimiento de dividendos 3Y.
- [ ] Calcular crecimiento de dividendos 5Y.
- [ ] Detectar dividend cuts.
- [ ] Detectar años sin dividendos.
- [ ] Crear `calculate_dividend_score()`.
- [ ] Guardar componentes del score.
- [ ] Añadir explicación legible.

---

# 6. EPIC 4 — Quality Score

## Objetivo

Evitar comprar una empresa simplemente porque está barata o tiene un yield elevado.

El modelo de calidad deberá cambiar según el tipo de activo.

---

## 6.1 Acciones tradicionales

Métricas iniciales:

- crecimiento de beneficios;
- payout ratio;
- deuda;
- ROE;
- ROIC;
- free cash flow;
- crecimiento de revenue;
- consistencia de dividendos.

Ejemplo:

```text
Quality Score

Dividend Growth      20%
Payout Safety        20%
Debt                 20%
Earnings Growth      20%
ROE / ROIC           10%
FCF Quality          10%
```

### Tareas

- [ ] Implementar normalización por métrica.
- [ ] Crear `StockQualityScorer`.
- [ ] Parametrizar pesos.
- [ ] Manejar valores faltantes.
- [ ] Evitar penalizar incorrectamente bancos.
- [ ] Crear perfiles de scoring por sector.

---

## 6.2 Bancos

No utilizar exactamente las mismas métricas de deuda que una empresa industrial.

Métricas futuras:

- ROE;
- CET1;
- payout;
- EPS growth;
- dividend growth;
- P/B;
- eficiencia;
- calidad de crédito.

### Tareas

- [ ] Crear `BankQualityScorer`.
- [ ] Definir métricas disponibles para Canadá y EE. UU.
- [ ] Crear fallback cuando no exista CET1.

---

## 6.3 REITs

No priorizar EPS/P-E.

Usar:

- AFFO per unit;
- AFFO growth;
- AFFO payout ratio;
- occupancy;
- debt / gross book value;
- interest coverage;
- distribución por unidad;
- crecimiento de distribución.

### Tareas

- [ ] Detectar activos REIT.
- [ ] Crear `REITQualityScorer`.
- [ ] Incorporar AFFO.
- [ ] Incorporar occupancy.
- [ ] Incorporar debt/GBV.
- [ ] Incorporar distribution growth.
- [ ] Evitar usar P/E como métrica principal.

---

# 7. EPIC 5 — Portfolio Fit Score

## Objetivo

Incorporar la composición actual de la cartera en la decisión.

### Fórmula base

```text
allocation_gap =
target_allocation
-
current_allocation
```

Ejemplo:

```text
             Actual     Target     Gap

TD             8.2%      10%      +1.8%
ENB           14.7%      10%      -4.7%
FTS            4.3%       8%      +3.7%
RY            12.1%      10%      -2.1%
```

### Tareas

- [ ] Permitir target allocation por activo.
- [ ] Permitir max allocation por activo.
- [ ] Permitir target allocation por sector.
- [ ] Permitir max allocation por sector.
- [ ] Permitir max allocation por país.
- [ ] Calcular current allocation.
- [ ] Calcular allocation gap.
- [ ] Crear `PortfolioFitScore`.
- [ ] Penalizar posiciones sobreponderadas.
- [ ] Bonificar posiciones subponderadas.
- [ ] Manejar portfolio sin targets definidos.

---

# 8. EPIC 6 — Opportunity Score

## Objetivo

Crear una puntuación final explicable de `0–100`.

### Fórmula inicial

```text
Opportunity Score =
Valuation Score      × 30%
+
Dividend Score       × 20%
+
Quality Score        × 30%
+
Portfolio Fit Score  × 20%
```

Los pesos deben depender de la estrategia.

### Tareas

- [ ] Crear `OpportunityScoreEngine`.
- [ ] Recibir strategy config.
- [ ] Calcular cada subscore.
- [ ] Combinar subscores.
- [ ] Guardar score final.
- [ ] Guardar breakdown.
- [ ] Guardar fecha/hora del cálculo.
- [ ] Crear explicación automática basada en reglas.
- [ ] Añadir unit tests.
- [ ] Añadir regression tests para cambios de modelo.

### Output sugerido

```json
{
  "ticker": "TD",
  "score": 84,
  "components": {
    "valuation": 80,
    "dividend": 90,
    "quality": 85,
    "portfolio_fit": 75
  },
  "reasons": [
    "Price is below selected ceiling",
    "Dividend yield is above its 5Y average",
    "Position is currently under target allocation"
  ]
}
```

---

# 9. EPIC 7 — Eligibility / Hard Rules

Antes de optimizar, algunos activos pueden ser descartados completamente.

### Ejemplos

```text
Current price > allowed ceiling
Position already exceeds max allocation
Sector already exceeds max allocation
Dividend cut detected
Insufficient fundamental data
Asset manually excluded
```

### Tareas

- [ ] Crear `EligibilityRule` interface.
- [ ] Implementar `BelowPriceCeilingRule`.
- [ ] Implementar `MaxPositionWeightRule`.
- [ ] Implementar `MaxSectorWeightRule`.
- [ ] Implementar `MinimumDividendYieldRule`.
- [ ] Implementar `MinimumQualityScoreRule`.
- [ ] Implementar `ManualExclusionRule`.
- [ ] Mostrar motivo cuando un activo sea descartado.

---

# 10. EPIC 8 — Motor de aporte simple (Greedy MVP)

## Objetivo

Tener una primera versión antes de implementar OR-Tools.

### Algoritmo

1. Filtrar activos no elegibles.
2. Calcular Opportunity Score.
3. Ordenar de mayor a menor.
4. Calcular cuánto necesita cada activo para llegar a su target.
5. Asignar dinero al mejor activo.
6. Continuar hasta agotar el aporte.

### Tareas

- [ ] Implementar `GreedyContributionAllocator`.
- [ ] Soportar fractional shares.
- [ ] Soportar activos sin fractional shares.
- [ ] Respetar amount disponible.
- [ ] Respetar target allocation.
- [ ] Respetar max allocation.
- [ ] Añadir explicación por asignación.
- [ ] Comparar resultado Greedy vs OR-Tools posteriormente.

---

# 11. EPIC 9 — Optimization Engine con OR-Tools

## Objetivo

Encontrar una distribución matemáticamente óptima del nuevo aporte.

Librería:

```text
Google OR-Tools
```

---

## 11.1 Modelo inicial

Variable por activo:

```text
x_i = cantidad de dinero asignada al activo i
```

Objetivo:

```text
Maximize:

Σ opportunity_score_i × x_i
```

Sujeto a:

```text
Σ x_i <= available_cash

x_i >= 0

new_position_weight_i <= max_position_weight_i

new_sector_weight <= max_sector_weight

x_i = 0 si el activo no es elegible
```

---

## 11.2 Modelo con target allocation

Mejorar la función objetivo para equilibrar oportunidad y diversificación.

Ejemplo:

```text
maximize:

Opportunity
-
AllocationDeviationPenalty
-
ConcentrationPenalty
```

Conceptualmente:

```text
maximize
Σ score_i × x_i
-
λ₁ × deviation_from_target
-
λ₂ × concentration_penalty
```

---

## 11.3 Tareas OR-Tools

- [ ] Instalar y configurar `ortools`.
- [ ] Crear módulo `optimization/`.
- [ ] Crear `ContributionOptimizer` interface.
- [ ] Crear `ORToolsContributionOptimizer`.
- [ ] Definir decision variables.
- [ ] Implementar constraint de cash.
- [ ] Implementar min investment amount.
- [ ] Implementar max investment por activo.
- [ ] Implementar max allocation por activo.
- [ ] Implementar max allocation por sector.
- [ ] Implementar max allocation por país.
- [ ] Implementar exclusiones.
- [ ] Implementar hard price ceiling.
- [ ] Implementar minimum score.
- [ ] Implementar target allocation penalty.
- [ ] Implementar concentration penalty.
- [ ] Implementar fractional shares.
- [ ] Implementar integer shares.
- [ ] Permitir mezcla entre fractional y non-fractional assets.
- [ ] Manejar cash residual.
- [ ] Añadir timeout del solver.
- [ ] Añadir fallback a Greedy si solver falla.
- [ ] Guardar solver status.
- [ ] Guardar objective value.
- [ ] Crear tests con portfolios pequeños.
- [ ] Comparar resultados contra escenarios manuales.

---

# 12. EPIC 10 — Optimización por número de acciones

Cuando un activo no permita fracciones:

```text
n_i = número entero de acciones a comprar
```

Entonces:

```text
investment_i =
n_i × current_price_i
```

Constraint:

```text
n_i ∈ Z>=0
```

Utilizar CP-SAT cuando corresponda.

### Tareas

- [ ] Detectar fractional eligibility.
- [ ] Crear variables enteras para acciones completas.
- [ ] Crear variables continuas/discretizadas para fractional shares.
- [ ] Evaluar `CP-SAT` vs `MIP`.
- [ ] Crear tests para portfolios mixtos.
- [ ] Mostrar cash no invertido.

---

# 13. EPIC 11 — Diversificación avanzada

## Restricciones opcionales

El usuario podrá configurar:

```text
Max per company      15%
Max per sector       30%
Max per country      80%
Max REIT exposure    20%
Min cash remaining    0%
```

### Tareas

- [ ] Exposure por sector.
- [ ] Exposure por industry.
- [ ] Exposure por país.
- [ ] Exposure por asset class.
- [ ] Exposure por currency.
- [ ] Exposure por account.
- [ ] Añadir constraints opcionales al solver.

---

# 14. EPIC 12 — Account-aware Optimization

## Objetivo

En el futuro el optimizador puede decidir no solo qué comprar, sino en qué cuenta.

Ejemplo:

```text
TFSA
RRSP
FHSA
Taxable
```

### Futuro

```text
Decision:

Asset × Account × Amount
```

### Consideraciones

- contribution room;
- withholding taxes;
- asset eligibility;
- currency;
- user preferences;
- registered vs non-registered accounts.

### Tareas

- [ ] Crear modelo de restricciones por account.
- [ ] Añadir contribution room.
- [ ] Añadir account-specific eligibility.
- [ ] Crear optimization variable `x_asset_account`.
- [ ] Añadir restricciones de cash por cuenta.
- [ ] Mantener esta lógica desacoplada del core scoring.

> Esta fase requiere revisión regulatoria/fiscal antes de presentarse como optimización tributaria.

---

# 15. EPIC 13 — Explicabilidad

## Objetivo

Cada recomendación debe poder responder:

```text
¿Por qué?
```

Sin LLM.

### Ejemplo

```text
FTS — 91/100

+20  Trading 14% below selected ceiling
+18  Dividend yield above 5Y average
+17  Dividend growth positive
+19  Strong quality score
+17  Portfolio currently underweight
```

### Tareas

- [ ] Crear `ScoreExplanation`.
- [ ] Crear mensajes por regla.
- [ ] Mostrar positivos.
- [ ] Mostrar negativos.
- [ ] Mostrar reglas que bloquearon compra.
- [ ] Mostrar valores utilizados.
- [ ] Añadir modal “How is this calculated?”.
- [ ] Mostrar fórmula y pesos de estrategia.
- [ ] Mostrar timestamp de los datos.

---

# 16. EPIC 14 — UI: “Next Contribution”

## Pantalla principal

Inputs:

```text
Amount to invest: C$1,000

Strategy:
[Bazin ▼]

Account:
[TFSA ▼]

Optimize for:
[x] Opportunity
[x] Target allocation
[x] Diversification
```

Resultado:

```text
Recommended allocation

FTS     C$480      91/100
TD      C$390      84/100
RY      C$130      71/100
```

### Tareas

- [ ] Input de aporte.
- [ ] Selector de estrategia.
- [ ] Selector de cuenta.
- [ ] Ranking de activos.
- [ ] Aporte sugerido.
- [ ] Score.
- [ ] Razones.
- [ ] Mostrar activos descartados.
- [ ] Mostrar cash residual.
- [ ] Mostrar estado antes/después del portfolio.
- [ ] Crear comparación target vs resulting allocation.

---

# 17. EPIC 15 — Before vs After Portfolio

Visualización:

```text
              BEFORE       AFTER       TARGET

TD              8.2%        9.1%       10%
FTS             4.3%        6.2%        8%
RY             12.1%       11.8%       10%
ENB            14.7%       14.1%       10%
```

### Tareas

- [ ] Simular cartera después del aporte.
- [ ] Calcular nuevas allocations.
- [ ] Mostrar desviación total respecto al target.
- [ ] Mostrar concentración antes/después.
- [ ] Mostrar estimated dividend income before/after.

---

# 18. EPIC 16 — Dividend Impact

Mostrar el efecto esperado del aporte sobre la renta.

Ejemplo:

```text
Current annual income:
C$2,480

Estimated after contribution:
C$2,528

Estimated increase:
+C$48/year
```

### Tareas

- [ ] Calcular forward dividend income.
- [ ] Estimar ingreso anual incremental.
- [ ] Mostrar yield del nuevo aporte.
- [ ] Mostrar portfolio yield antes/después.
- [ ] No presentar proyecciones como garantizadas.

---

# 19. EPIC 17 — Estrategias predefinidas

## Bazin

Priorizar:

```text
40% valuation / ceiling
25% dividend
20% quality
15% portfolio fit
```

## Dividend Growth

```text
20% valuation
20% yield
25% dividend growth
20% quality
15% portfolio fit
```

## Quality

```text
15% valuation
10% dividend
50% quality
25% portfolio fit
```

## Balanced

```text
25% valuation
20% dividend
30% quality
25% portfolio fit
```

### Tareas

- [ ] Crear presets.
- [ ] Documentar fórmula.
- [ ] Versionar presets.
- [ ] Permitir clonar preset.
- [ ] Permitir personalizar copia.

---

# 20. EPIC 18 — Strategy Builder

## Objetivo

Permitir que el usuario cree sus propias reglas.

Ejemplo:

```text
My Dividend Strategy

Minimum DY                   3%
Minimum dividend growth      5%
Maximum payout              70%
Maximum Debt/Equity          1.5
Minimum ROE                 12%
Maximum position            15%

Use Bazin ceiling           ON
```

### Tareas

- [ ] UI builder.
- [ ] Pesos custom.
- [ ] Thresholds custom.
- [ ] Hard rule vs soft preference.
- [ ] Validación de pesos = 100%.
- [ ] Preview de cómo cambia el ranking.
- [ ] Guardar múltiples estrategias.
- [ ] Duplicar estrategia.
- [ ] Reset to default.

---

# 21. EPIC 19 — Backtesting del scoring

Antes de confiar en un score, probarlo históricamente.

Preguntas:

```text
¿Las empresas con score alto tuvieron mejor comportamiento?
¿El score favorece demasiado un sector?
¿Un yield elevado está introduciendo value traps?
¿El price ceiling mejora el resultado?
```

### Tareas

- [ ] Guardar snapshots históricos.
- [ ] Reconstruir scores históricos.
- [ ] Crear portfolios por deciles.
- [ ] Comparar retorno total.
- [ ] Comparar dividend growth.
- [ ] Comparar drawdown.
- [ ] Comparar volatilidad.
- [ ] Analizar survivorship bias.
- [ ] Analizar look-ahead bias.
- [ ] Versionar scoring models.

---

# 22. EPIC 20 — Testing

## Unit Tests

- [ ] Bazin ceiling.
- [ ] Valuation score.
- [ ] Dividend score.
- [ ] Quality score.
- [ ] Portfolio fit.
- [ ] Opportunity score.
- [ ] Hard eligibility rules.
- [ ] Greedy allocation.
- [ ] OR-Tools constraints.

## Scenario Tests

- [ ] Todo el portfolio está sobrevalorado.
- [ ] Un solo activo es elegible.
- [ ] Todos están sobreponderados.
- [ ] No existen targets.
- [ ] No hay dividend history.
- [ ] Cash menor al precio de una acción.
- [ ] Fractional shares permitidas.
- [ ] Fractional shares no permitidas.
- [ ] Score empatado.
- [ ] Sector cap alcanzado.
- [ ] OR-Tools infeasible.
- [ ] Solver timeout.
- [ ] Datos fundamentales incompletos.

---

# 23. EPIC 21 — Observabilidad

### Tareas

- [ ] Loggear strategy usada.
- [ ] Loggear score version.
- [ ] Loggear solver status.
- [ ] Loggear optimization duration.
- [ ] Loggear número de candidatos.
- [ ] Loggear constraints activas.
- [ ] Registrar fallback Greedy.
- [ ] Métrica de infeasible optimizations.
- [ ] Métrica de solver timeout.
- [ ] Métrica de utilización de la feature.

---

# 24. EPIC 22 — Compliance / Product Language

Evitar mensajes como:

```text
Buy TD now.
```

Preferir:

```text
Based on your selected strategy,
TD currently has the highest fit score.
```

o:

```text
This allocation best matches the rules
you configured for your portfolio.
```

### Tareas

- [ ] Revisar lenguaje de UI.
- [ ] Añadir disclaimer.
- [ ] Diferenciar score de recomendación financiera.
- [ ] Mostrar que los datos pueden tener retraso.
- [ ] Mostrar que dividendos futuros no están garantizados.
- [ ] Revisar requirements regulatorios antes de monetizar la feature.

---

# 25. Estructura de código sugerida

```text
app/
│
├── domain/
│   ├── portfolio/
│   ├── assets/
│   ├── strategies/
│   └── scoring/
│
├── scoring/
│   ├── valuation.py
│   ├── dividends.py
│   ├── quality/
│   │   ├── stocks.py
│   │   ├── banks.py
│   │   └── reits.py
│   ├── portfolio_fit.py
│   └── opportunity.py
│
├── optimization/
│   ├── base.py
│   ├── greedy.py
│   ├── ortools_optimizer.py
│   ├── constraints.py
│   └── objective.py
│
├── strategies/
│   ├── bazin.py
│   ├── dividend_growth.py
│   ├── quality.py
│   └── balanced.py
│
└── services/
    └── next_contribution_service.py
```

---

# 26. Interfaces sugeridas

```python
class Scorer:
    def score(self, asset, portfolio, strategy):
        ...
```

```python
class ContributionOptimizer:
    def optimize(
        self,
        portfolio,
        candidates,
        amount,
        strategy,
    ):
        ...
```

Implementaciones:

```text
GreedyContributionOptimizer
ORToolsContributionOptimizer
```

Esto permite cambiar el algoritmo sin modificar la capa de producto.

---

# 27. Fases de implementación

## Fase 1 — Scoring MVP

- [ ] Bazin ceiling.
- [ ] Valuation Score.
- [ ] Dividend Score.
- [ ] Portfolio Fit.
- [ ] Opportunity Score.
- [ ] Explicaciones.
- [ ] Ranking.

### Resultado

```text
Best candidates for your next contribution
```

sin sugerir todavía cantidades óptimas.

---

## Fase 2 — Greedy Allocation

- [ ] Input del aporte.
- [ ] Target allocations.
- [ ] Max allocations.
- [ ] Greedy allocator.
- [ ] Before/after portfolio.
- [ ] Dividend impact.

### Resultado

TrueNorth ya puede distribuir un aporte.

---

## Fase 3 — OR-Tools v1

- [ ] Linear/MIP model.
- [ ] Cash constraint.
- [ ] Position caps.
- [ ] Sector caps.
- [ ] Eligibility constraints.
- [ ] Opportunity objective.
- [ ] Greedy fallback.

### Resultado

Distribución optimizada matemáticamente.

---

## Fase 4 — OR-Tools v2

- [ ] Target deviation penalty.
- [ ] Concentration penalty.
- [ ] Integer shares.
- [ ] Fractional shares.
- [ ] Currency constraints.
- [ ] Account-aware constraints.

---

## Fase 5 — Strategy Builder

- [ ] Custom weights.
- [ ] Custom thresholds.
- [ ] Custom hard rules.
- [ ] Multiple strategies.
- [ ] Strategy presets.

---

## Fase 6 — Advanced Intelligence

Sin LLM.

- [ ] Historical percentile scoring.
- [ ] Sector-relative metrics.
- [ ] Dividend safety score.
- [ ] REIT-specific scoring.
- [ ] Bank-specific scoring.
- [ ] Backtesting.
- [ ] Portfolio optimization by account.
- [ ] Tax-aware constraints donde legalmente corresponda.

---

# 28. Definición de Done para la feature

La feature se considera madura cuando:

- [ ] El mismo input siempre produce el mismo resultado.
- [ ] Cada score puede explicarse matemáticamente.
- [ ] Cada activo descartado muestra el motivo.
- [ ] El usuario puede cambiar estrategia.
- [ ] El usuario puede configurar targets.
- [ ] El usuario puede configurar límites.
- [ ] El aporte respeta todas las restricciones.
- [ ] OR-Tools encuentra una solución válida o existe fallback.
- [ ] El resultado muestra portfolio antes/después.
- [ ] El resultado muestra dividend income estimado antes/después.
- [ ] Los cálculos están cubiertos por tests.
- [ ] El modelo de scoring está versionado.
- [ ] La UI evita lenguaje que parezca una recomendación financiera personalizada no calificada.

---

# 29. Idea central

La verdadera ventaja de esta feature no sería que TrueNorth “te diga qué comprar”.

Sería esto:

> **TrueNorth toma la estrategia del usuario, los fundamentales de sus empresas, la valoración actual y la composición de su cartera, y calcula la distribución del próximo aporte que mejor satisface esas reglas.**

El núcleo puede ser completamente determinístico:

```text
DATA
  +
RULES
  +
SCORING
  +
OR-TOOLS OPTIMIZATION
  =
NEXT CONTRIBUTION ENGINE
```

Sin LLMs.

Eso hace la feature:

- explicable;
- testeable;
- auditable;
- reproducible;
- configurable;
- escalable;
- mucho más apropiada para un producto financiero serio.
