# Modelo de Datos Objetivo

```mermaid
erDiagram
    User ||--o{ Order : places
    User ||--o{ PortfolioSnapshot : has
    User ||--o{ DividendReceived : receives
    User ||--o{ AllocationTarget : defines
    Asset ||--o{ Order : "traded in"
    Asset ||--o{ Fundamentals : "snapshots"
    Asset ||--o{ DividendHistory : pays
    Asset ||--o{ PriceHistory : "EOD prices"
    Asset ||--o{ CompanyEvent : announces
    Order }o--|| Account : "belongs to"
    DividendHistory ||--o{ DividendReceived : generates

    Asset {
        int id PK
        string symbol "RY"
        string yahoo_symbol "RY.TO"
        string exchange "TSX|TSXV|NYSE|NASDAQ"
        string currency "CAD|USD"
        string name
        string sector
        string industry
        string website
        string ir_website "link relaciones con inversores"
        string logo_url
        bool is_active
    }

    Fundamentals {
        int id PK
        int asset_id FK
        date as_of_date
        float price
        float market_cap
        float pe
        float forward_pe
        float pb
        float ps
        float ev_ebitda
        float roe
        float roa
        float roic
        float gross_margin
        float operating_margin
        float net_margin
        float debt_to_equity
        float current_ratio
        float dividend_yield
        float payout_ratio
        float eps
        float beta
    }

    Order {
        int id PK
        int user_id FK
        int asset_id FK
        int account_id FK
        enum type "BUY|SELL"
        float quantity
        float price
        float fees
        string currency
        float fx_rate_to_cad
        datetime executed_at
        string broker
        string import_hash "dedupe"
    }

    Account {
        int id PK
        int user_id FK
        enum type "TFSA|RRSP|FHSA|MARGIN|CASH"
        string name
        string broker
    }

    DividendHistory {
        int id PK
        int asset_id FK
        date ex_date
        date pay_date
        float amount
        string currency
    }

    DividendReceived {
        int id PK
        int user_id FK
        int asset_id FK
        date pay_date
        float quantity_held
        float total_amount
        string currency
        bool confirmed
    }

    PortfolioSnapshot {
        int id PK
        int user_id FK
        date date
        float patrimony_cad
        float total_invested_cad
        float dividends_accum_cad
    }

    PriceHistory {
        int id PK
        int asset_id FK
        date date
        float close
        float adj_close
        int volume
    }

    CompanyEvent {
        int id PK
        int asset_id FK
        enum kind "FILING|DIVIDEND|EARNINGS|NEWS"
        string title
        string url
        datetime published_at
        string source "EDGAR|SEDAR|NEWS"
    }

    FxRate {
        date date PK
        string pair "USDCAD"
        float rate
    }

    AllocationTarget {
        int id PK
        int user_id FK
        int asset_id FK
        float target_percent
    }
```

## Notas de diseño

- **Posiciones derivadas**: no hay tabla `Portfolio` editable — la posición actual se calcula
  desde `Order` (cacheable en memoria o vista materializada regenerable). Evita el bug actual
  de duplicación en cada import.
- **Fundamentals como snapshots**: una fila por asset por día de refresh → permite gráficos de
  evolución de P/E, DY histórico, etc. Vista `latest_fundamentals` para el screener.
- **Average cost (CRA)**: el costo promedio se calcula global por asset entre cuentas no
  registradas (regla canadiense); en TFSA/RRSP no tributa pero se muestra igual.
- **`import_hash`**: hash de (fecha, símbolo, tipo, qty, precio, broker) para no duplicar
  órdenes al re-importar el mismo CSV.
- **FX**: toda métrica agregada del portafolio se muestra en CAD usando `FxRate` del día; la
  orden guarda el fx del día de ejecución para el costo real.
