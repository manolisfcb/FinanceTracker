# Implementar método de análisis para ETFs de Income / Covered Call

Quiero crear dentro de la plataforma un nuevo método cuantitativo para analizar ETFs orientados a generación de ingresos, especialmente:

* Dividend ETFs
* Income ETFs
* Covered Call ETFs
* Enhanced Covered Call ETFs

Este método debe funcionar de forma similar a los métodos existentes de Bazin o Graham: debe ser **determinístico y basado exclusivamente en datos**, sin utilizar LLMs para realizar el análisis.

El mismo ETF con los mismos datos siempre debe producir exactamente el mismo resultado.

Nombre provisional:

`Income ETF Quality Model`

o

`Income ETF Score`

---

# Objetivo

El objetivo NO es encontrar simplemente ETFs con el mayor distribution yield.

El algoritmo debe determinar si un ETF es capaz de:

1. generar distribuciones atractivas;
2. mantenerlas de forma relativamente estable;
3. preservar el capital/NAV;
4. producir un total return razonable;
5. mantener activos subyacentes de calidad;
6. evitar distribuciones artificialmente altas acompañadas de destrucción de capital.

El modelo debe detectar posibles `yield traps`.

---

# 1. Datos necesarios

Crear una estructura `ETFAnalysisData`.

Debe incluir como mínimo:

```python
ticker
inception_date
current_price
current_nav
aum
mer
management_fee
risk_rating

distribution_frequency
current_distribution
current_distribution_yield

distribution_history

nav_history
price_history

total_return_1y
total_return_3y
total_return_5y
total_return_10y

return_of_capital_history
dividend_income_history
option_income_history
capital_gain_distribution_history

number_of_holdings
sector_weights
country_weights

covered_call_percentage
uses_leverage
leverage_percentage
```

Cuando algún dato no esté disponible, el algoritmo debe poder continuar con los componentes disponibles y calcular también un `data_confidence_score`.

---

# 2. ETF Age Score

Queremos favorecer ETFs con historial suficiente.

```text
< 3 años       = 2/10
3-5 años       = 4/10
5-10 años      = 7/10
10-15 años     = 9/10
> 15 años      = 10/10
```

Este score no mide rendimiento. Mide confianza histórica.

---

# 3. Income Yield Score

Evaluar el distribution yield actual.

```text
< 3%       = 3
3-5%       = 5
5-7%       = 8
7-10%      = 10
10-12%     = 9
12-15%     = 7
15-20%     = 5
>20%       = 2
```

Importante:

Un yield extremadamente alto NO debe producir automáticamente un score superior.

Queremos penalizar yields potencialmente insostenibles.

Peso recomendado:

`10%`

---

# 4. Distribution Stability Score

Utilizar como mínimo los últimos 5 años de distribuciones.

Calcular por año:

```python
annual_distribution[year] = sum(distributions)
```

Calcular:

```python
distribution_cagr
distribution_std
distribution_cv
years_with_distribution_cut
largest_distribution_cut
```

Donde:

```python
CV = std(annual_distribution) / mean(annual_distribution)
```

Score inicial:

```text
CV < 5%       = 10
5-10%         = 9
10-15%        = 8
15-25%        = 6
25-40%        = 4
>40%          = 2
```

Penalizaciones:

```text
cada año con reducción       -1
reducción >10%               -1 adicional
reducción >25%               -2 adicionales
```

Bonus:

```text
5 años sin reducción         +1
CAGR distribución >3%        +1
```

Limitar resultado:

```python
score = min(10, max(0, score))
```

Peso:

`15%`

---

# 5. NAV Preservation Score

Este debe ser uno de los componentes MÁS importantes.

Queremos detectar ETFs que pagan distribuciones enormes mientras destruyen su NAV.

Calcular:

```python
nav_cagr_5y
nav_cagr_10y
nav_drawdown
nav_recovery
```

Score usando principalmente CAGR de NAV a largo plazo:

```text
NAV CAGR >5%       = 10
3-5%               = 9
1-3%               = 8
0-1%               = 7
-1%-0%             = 6
-3% a -1%          = 4
-5% a -3%          = 2
< -5%              = 0
```

No penalizar automáticamente un año negativo.

La prioridad es detectar una tendencia estructural de largo plazo.

Ejemplo saludable:

```text
10 → 11 → 9 → 11 → 12
```

Ejemplo preocupante:

```text
20 → 17 → 14 → 11 → 8
```

Peso:

`20%`

---

# 6. Total Return Score

Este será el componente de mayor importancia junto con NAV preservation.

Utilizar:

```python
total_return_5y
total_return_10y
```

Preferiblemente retornos anualizados incluyendo distribuciones.

Score orientativo:

```text
>12%       = 10
10-12%     = 9
8-10%      = 8
6-8%       = 7
4-6%       = 5
2-4%       = 3
0-2%       = 2
<0%        = 0
```

Si existen ambos:

```python
long_term_return =
    total_return_5y * 0.40 +
    total_return_10y * 0.60
```

Dar mayor importancia a 10 años.

Si no existen 10 años:

usar 5 años y reducir `data_confidence`.

Peso:

`20%`

---

# 7. Distribution Coverage / ROC Score

Calcular para cada año:

```python
roc_ratio =
    return_of_capital /
    total_distributions
```

Después calcular:

```python
average_roc_5y
```

Score inicial:

```text
ROC 0-10%      = 10
10-20%         = 9
20-30%         = 8
30-40%         = 7
40-50%         = 6
50-60%         = 5
60-75%         = 3
>75%           = 1
```

IMPORTANTE:

ROC NO debe penalizarse automáticamente.

Antes de aplicar una penalización fuerte comprobar:

```python
if high_ROC and NAV_is_stable and total_return_is_positive:
    reduce_ROC_penalty()
```

Por ejemplo:

Un ETF con:

```text
ROC = 40%
NAV CAGR = +2%
Total Return = 10%
```

puede ser saludable.

Pero:

```text
ROC = 70%
NAV CAGR = -6%
Total Return = 1%
```

es una señal muy preocupante.

Peso:

`10%`

---

# 8. Diversification Score

Evaluar:

```python
number_of_holdings
largest_holding_weight
top_10_weight
largest_sector_weight
largest_country_weight
```

Ejemplo base:

```text
100+ holdings       = 10
50-99               = 9
30-49               = 8
20-29               = 7
10-19               = 5
<10                 = 2
```

Aplicar penalizaciones por concentración.

Ejemplo:

```python
if largest_holding > 15%:
    score -= 2

if largest_sector > 50%:
    score -= 2
```

No penalizar excesivamente ETFs cuyo mandato sea explícitamente sectorial.

En esos casos marcar:

```python
concentration_risk = HIGH
```

en lugar de destruir completamente el score.

Peso:

`5%`

---

# 9. Cost Efficiency Score

Utilizar MER.

```text
<0.20%       = 10
0.20-0.40%   = 9
0.40-0.60%   = 8
0.60-0.80%   = 7
0.80-1.00%   = 6
1.00-1.25%   = 4
>1.25%       = 2
```

Peso:

`5%`

---

# 10. Covered Call Strategy Score

Aplicar solamente si:

```python
uses_covered_calls == True
```

Utilizar:

```python
covered_call_percentage
```

Como regla inicial:

```text
0-25%       = 9
25-40%      = 10
40-50%      = 9
50-75%      = 7
75-100%     = 5
```

La lógica es que una cobertura extremadamente alta puede limitar demasiado el upside.

Este componente debe analizarse junto con total return.

Si:

```python
covered_call_percentage > 75
and total_return_5y < benchmark_return_5y - 4
```

aplicar penalización adicional.

Peso:

`5%`

---

# 11. Leverage Risk

Si el ETF utiliza leverage:

```python
uses_leverage == True
```

aplicar una penalización separada.

```text
0%          = 0
<10%        = -1
10-25%      = -3
25-40%      = -5
>40%        = -8
```

Esta penalización se aplica sobre el score final de 0-100.

Nunca permitir score <0.

---

# 12. Yield Trap Detection

Crear un algoritmo independiente:

```python
yield_trap_risk()
```

Debe analizar conjuntamente:

```text
distribution_yield
NAV CAGR
total return
distribution cuts
ROC
leverage
```

Ejemplos de señales:

```python
yield > 12%
NAV_CAGR_5Y < -2%

yield > 15%
total_return_5Y < 4%

ROC > 60%
NAV_CAGR_5Y < 0%

distribution_cuts >= 2

NAV_CAGR_5Y < -5%
```

No utilizar una sola condición para determinar que existe un yield trap.

Crear `yield_trap_points`.

Ejemplo:

```text
Yield >12%                         +1
Yield >18%                         +1
NAV CAGR < -2%                     +2
NAV CAGR < -5%                     +2
Total return <4%                   +2
ROC >60%                           +1
ROC >60% + NAV declining           +2
2+ distribution cuts               +1
Leverage >25%                      +1
```

Clasificación:

```text
0-2     LOW
3-5     MODERATE
6-8     HIGH
9+      VERY HIGH
```

---

# 13. Final Score

Calcular:

```python
score = (
    income_yield_score * 0.10 +
    distribution_stability_score * 0.15 +
    nav_preservation_score * 0.20 +
    total_return_score * 0.20 +
    distribution_quality_score * 0.10 +
    diversification_score * 0.05 +
    cost_efficiency_score * 0.05 +
    covered_call_score * 0.05 +
    age_score * 0.10
)
```

Convertir de escala 0-10 a 0-100.

Después aplicar:

```python
score -= leverage_penalty
score -= yield_trap_penalty
```

Mantener:

```python
0 <= score <= 100
```

---

# 14. Clasificación

```text
90-100   A+   Exceptional Income ETF
85-89    A    Strong
80-84    A-   Very Good

75-79    B+   Good
70-74    B    Acceptable
65-69    B-   Acceptable with concerns

60-64    C+   Significant trade-offs
50-59    C    High caution
40-49    D    High risk
<40      F    Potential Yield Trap
```

IMPORTANTE:

El grade debe representar la calidad del ETF **como vehículo de generación de income**, no como inversión universal.

---

# 15. Data Confidence Score

Crear además:

```python
data_confidence_score
```

Ejemplo:

```text
10+ años historial               +25
5+ años distribuciones           +20
NAV histórico disponible         +15
ROC disponible                   +15
Total return disponible          +15
Holdings disponibles             +5
Covered call data disponible     +5
```

Resultado:

```text
85-100 HIGH
65-84  MEDIUM
<65    LOW
```

Mostrar siempre este valor junto al score.

---

# 16. Resultado del método

El backend debe devolver una estructura similar a:

```json
{
    "ticker": "HBF",

    "income_etf_score": 82,
    "grade": "A-",

    "yield_trap_risk": "LOW",

    "data_confidence": {
        "score": 94,
        "level": "HIGH"
    },

    "metrics": {
        "distribution_yield": 8.09,
        "nav_cagr_5y": 1.8,
        "total_return_5y": 7.0,
        "total_return_10y": 10.57,
        "average_roc_5y": 35.2,
        "mer": 0.88
    },

    "scores": {
        "income": 10,
        "distribution_stability": 8,
        "nav_preservation": 8,
        "total_return": 8,
        "distribution_quality": 7,
        "diversification": 7,
        "cost_efficiency": 6,
        "covered_call_strategy": 9,
        "age": 9
    },

    "flags": [
        "HIGH_ROC",
        "COVERED_CALL",
        "MEDIUM_CONCENTRATION"
    ]
}
```

Los valores anteriores de HBF son solamente un ejemplo del formato. No hardcodearlos.

---

# 17. Arquitectura

Separar completamente:

```text
Raw ETF Data
      ↓
ETF Metrics Calculator
      ↓
Income ETF Scoring Engine
      ↓
Risk / Yield Trap Engine
      ↓
ETF Analysis Result
      ↓
API
      ↓
Frontend
```

Crear funciones independientes y testeables:

```python
calculate_distribution_metrics()
calculate_nav_metrics()
calculate_total_return_metrics()
calculate_roc_metrics()
calculate_diversification_metrics()

score_income()
score_distribution_stability()
score_nav_preservation()
score_total_return()
score_distribution_quality()
score_diversification()
score_cost_efficiency()
score_covered_call_strategy()

calculate_yield_trap_risk()
calculate_data_confidence()
calculate_income_etf_score()
```

No mezclar adquisición de datos con scoring.

El scoring engine debe recibir datos ya normalizados.

---

# 18. Principio fundamental

El algoritmo debe favorecer:

**Income + Preservation of Capital + Total Return**

y NO:

**Maximum Yield**

Por tanto:

```text
ETF A
Yield 8%
NAV estable
10Y return 10%
Distribución estable
```

debe poder obtener una puntuación superior a:

```text
ETF B
Yield 18%
NAV cayendo -6% anual
10Y return 3%
ROC elevado
Distribuciones decrecientes
```

aunque ETF B produzca mucho más cash actualmente.
