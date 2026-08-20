"""Side-by-side company comparison assembled from latest fundamentals."""

from math import isfinite

from src.services.insights import INDICATOR_RULES, assess_indicator, build_company_insight


# key, display label, format, better direction. Rows mirror the dense layout
# of the supplied comparator while using only fields the app can audit.
COMPARISON_GROUPS = (
    ("Valuación", (
        ("pe", "P/L", "ratio", "lower"),
        ("forward_pe", "P/L proyectado", "ratio", "lower"),
        ("pb", "P/VP", "ratio", "lower"),
        ("ps", "P/ventas", "ratio", "lower"),
        ("ev_ebitda", "EV/EBITDA", "ratio", "lower"),
        ("ev_ebit", "EV/EBIT", "ratio", "lower"),
        ("p_ebit", "P/EBIT", "ratio", "lower"),
        ("price_to_assets", "P/activos", "ratio", "lower"),
    )),
    ("Eficiencia y rentabilidad", (
        ("gross_margin", "Margen bruto", "percent", "higher"),
        ("operating_margin", "Margen EBIT", "percent", "higher"),
        ("ebitda_margin", "Margen EBITDA", "percent", "higher"),
        ("net_margin", "Margen neto", "percent", "higher"),
        ("roe", "ROE", "percent", "higher"),
        ("roa", "ROA", "percent", "higher"),
        ("roic", "ROIC", "percent", "higher"),
        ("asset_turnover", "Giro del activo", "ratio", "higher"),
    )),
    ("Solidez", (
        ("net_debt_to_equity", "Deuda neta/patr.", "ratio", "lower"),
        ("net_debt_to_ebitda", "Deuda neta/EBITDA", "ratio", "lower"),
        ("debt_to_equity", "Deuda/patr.", "ratio", "lower"),
        ("liabilities_to_assets", "Pasivo/activos", "percent", "lower"),
        ("current_ratio", "Liquidez corriente", "ratio", "higher"),
        ("quick_ratio", "Liquidez seca", "ratio", "higher"),
    )),
    ("Crecimiento y dividendos", (
        ("revenue_cagr", "CAGR ingresos", "percent", "higher"),
        ("revenue_growth_5y", "Ingresos a/a", "percent", "higher"),
        ("eps_growth_5y", "BPA a/a", "percent", "higher"),
        ("dividend_yield", "Dividend yield", "percent", "higher"),
        ("payout_ratio", "Payout", "percent", "lower"),
    )),
)


def _number(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _positions(values, direction):
    available = [(index, value) for index, value in enumerate(values) if value is not None]
    available.sort(key=lambda pair: pair[1], reverse=direction == "higher")
    positions = {}
    previous_value = object()
    previous_rank = 0
    for index, value in available:
        if value != previous_value:
            previous_rank = len(positions) + 1
            previous_value = value
        positions[index] = previous_rank
    return positions


def build_comparison(rows):
    """Return display-ready columns and ranked indicator groups for 2–4 rows."""
    columns = []
    for asset, fundamentals in rows:
        columns.append({
            "asset": asset,
            "fundamentals": fundamentals,
            "insight": build_company_insight(asset, fundamentals),
        })

    groups = []
    for group_name, definitions in COMPARISON_GROUPS:
        metrics = []
        for key, label, format_kind, direction in definitions:
            values = [
                _number(getattr(column["fundamentals"], key, None))
                if column["fundamentals"] else None
                for column in columns
            ]
            # Negative valuation multiples do not mean "cheapest".
            if direction == "lower" and key in {"pe", "forward_pe", "pb", "ps", "ev_ebitda", "ev_ebit", "p_ebit", "price_to_assets"}:
                values = [value if value is not None and value > 0 else None for value in values]
            positions = _positions(values, direction)
            cells = []
            for index, (column, value) in enumerate(zip(columns, values)):
                signal = None
                if key in INDICATOR_RULES:
                    signal = assess_indicator(key, value, column["asset"].sector)
                cells.append({
                    "value": value,
                    "rank": positions.get(index),
                    "signal": signal,
                })
            metrics.append({
                "key": key,
                "label": label,
                "format": format_kind,
                "cells": cells,
            })
        groups.append({"name": group_name, "metrics": metrics})

    overall_positions = _positions(
        [column["insight"]["score"] for column in columns],
        "higher",
    )
    for index, column in enumerate(columns):
        column["overall_rank"] = overall_positions.get(index)
        column["rank_counts"] = {
            rank: sum(
                cell["rank"] == rank
                for group in groups
                for metric in group["metrics"]
                for cell_index, cell in enumerate(metric["cells"])
                if cell_index == index
            )
            for rank in range(1, 5)
        }
    return {"columns": columns, "groups": groups}


def normalize_price_history(history):
    """Convert EOD closes into percentage return from the first observation."""
    usable = [point for point in history if _number(point.get("close")) not in (None, 0)]
    if not usable:
        return []
    baseline = float(usable[0]["close"])
    return [
        {
            "date": point["date"],
            "value": round((float(point["close"]) / baseline - 1) * 100, 4),
        }
        for point in usable
    ]
