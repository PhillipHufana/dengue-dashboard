# api/timeseries.py
from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from .supabase_client import get_supabase
from .utils import normalize_name  # must match how "name" is stored in Supabase

router = APIRouter(tags=["Timeseries"])


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

MODEL_COLUMN_MAP: Dict[str, str] = {
    "preferred": "final_forecast",  # your best / ensemble
    "final": "final_forecast",
    "hybrid": "hybrid_forecast",
    "local": "local_forecast",
}


def _resample_series(
    rows: List[Dict[str, Any]],
    freq: Literal["weekly", "monthly", "yearly"],
) -> List[Dict[str, Any]]:
    """
    rows: list of {"date": "YYYY-MM-DD", "cases": ..., "forecast": ...}
    freq: "weekly" | "monthly" | "yearly"
    Aggregates by sum.
    """
    if freq == "weekly":
        # Already weekly, just sort and return
        return sorted(rows, key=lambda r: r["date"])

    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if df.empty:
        return []

    if freq == "monthly":
        rule = "MS"  # month start
    elif freq == "yearly":
        rule = "YS"  # year start
    else:
        # Should not happen, as we validate freq earlier
        return rows

    agg = (
        df.groupby(pd.Grouper(key="date", freq=rule))
        .agg(
            cases=("cases", "sum"),
            forecast=("forecast", "sum"),
        )
        .reset_index()
    )

    result: List[Dict[str, Any]] = []
    for _, row in agg.iterrows():
        result.append(
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "cases": float(row["cases"]) if pd.notna(row["cases"]) else None,
                "forecast": float(row["forecast"]) if pd.notna(row["forecast"]) else None,
            }
        )
    return result


# ------------------------------------------------------------
# Main endpoint
# ------------------------------------------------------------

@router.get("")
def get_timeseries(
    level: Literal["barangay", "city"] = Query("barangay"),
    name: Optional[str] = Query(None, description="Required when level=barangay"),
    freq: Literal["weekly", "monthly", "yearly"] = Query(
        "weekly", description="Aggregation level"
    ),
    model: Literal["preferred", "final", "hybrid", "local"] = Query(
        "preferred", description="Which forecast column to use"
    ),
):
    """
    Unified timeseries endpoint.

    - level=barangay, name="buhangin"
    - level=city

    Returns:
    {
      "level": "barangay",
      "name": "buhangin",
      "freq": "weekly",
      "model": "preferred",
      "n_points": 52,
      "series": [
        {"date": "2024-01-01", "cases": 2, "forecast": null},
        {"date": "2024-01-08", "cases": 0, "forecast": 0.3},
        ...
      ]
    }
    """
    sb = get_supabase()

    # Which forecast column to read
    forecast_col = MODEL_COLUMN_MAP.get(model)
    if forecast_col is None:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")

    # --------------------------------------------------------
    # BARANGAY LEVEL
    # --------------------------------------------------------
    if level == "barangay":
        if not name:
            raise HTTPException(status_code=400, detail="name is required when level=barangay")

        nm = normalize_name(name)

        # 1) Historical weekly cases for this barangay
        weekly_resp = (
            sb.table("barangay_weekly")
            .select("week_start, cases")
            .eq("name", nm)
            .order("week_start")
            .execute()
        )
        weekly_rows = weekly_resp.data or []

        # 2) Forecasts for this barangay (all weeks)
        fore_resp = (
            sb.table("barangay_forecasts")
            .select(f"week_start, {forecast_col}, is_future")
            .eq("name", nm)
            .order("week_start")
            .execute()
        )
        fore_rows = fore_resp.data or []

        if not weekly_rows and not fore_rows:
            raise HTTPException(
                status_code=404,
                detail=f"No timeseries found for barangay '{name}' (normalized='{nm}')",
            )

        # 3) Merge into single dictionary keyed by date
        series_map: Dict[str, Dict[str, Any]] = {}

        # Historical cases
        for row in weekly_rows:
            d = row["week_start"]
            series_map.setdefault(
                d,
                {"date": d, "cases": None, "forecast": None},
            )
            series_map[d]["cases"] = row.get("cases")

        # Forecasts (selected model)
        for row in fore_rows:
            d = row["week_start"]
            val = row.get(forecast_col)
            if val is None:
                continue
            series_map.setdefault(
                d,
                {"date": d, "cases": None, "forecast": None},
            )
            series_map[d]["forecast"] = float(val)

        # Convert to sorted list
        series = sorted(series_map.values(), key=lambda r: r["date"])

        # Resample if needed
        series = _resample_series(series, freq=freq)

        return {
            "level": "barangay",
            "name": nm,
            "freq": freq,
            "model": model,
            "n_points": len(series),
            "series": series,
        }

    # --------------------------------------------------------
    # CITY LEVEL
    # --------------------------------------------------------
    # 1) Historical city cases
    city_resp = (
        sb.table("city_weekly")
        .select("week_start, city_cases")
        .order("week_start")
        .execute()
    )
    city_rows = city_resp.data or []

    if not city_rows:
        raise HTTPException(status_code=404, detail="No city_weekly data found")

    # 2) Aggregate barangay forecasts → city forecast per week
    fore_resp = (
        sb.table("barangay_forecasts")
        .select(f"week_start, {forecast_col}")
        .order("week_start")
        .execute()
    )
    fore_rows = fore_resp.data or []

    # Sum forecast per week_start
    city_fore_map: Dict[str, float] = {}
    for row in fore_rows:
        d = row["week_start"]
        val = row.get(forecast_col)
        if val is None:
            continue
        city_fore_map[d] = city_fore_map.get(d, 0.0) + float(val)

    # Merge into series_map
    series_map: Dict[str, Dict[str, Any]] = {}
    for row in city_rows:
        d = row["week_start"]
        series_map.setdefault(
            d,
            {"date": d, "cases": None, "forecast": None},
        )
        series_map[d]["cases"] = row.get("city_cases")

    for d, total_fore in city_fore_map.items():
        series_map.setdefault(
            d,
            {"date": d, "cases": None, "forecast": None},
        )
        series_map[d]["forecast"] = total_fore

    series = sorted(series_map.values(), key=lambda r: r["date"])
    series = _resample_series(series, freq=freq)

    return {
        "level": "city",
        "name": None,
        "freq": freq,
        "model": model,
        "n_points": len(series),
        "series": series,
    }
