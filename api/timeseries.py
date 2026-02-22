# api/timeseries.py
from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from .supabase_client import get_supabase
from .utils import normalize_name  # must match how "name" is stored in Supabase
from .run_helpers import resolve_run_id, resolve_model_name

router = APIRouter(tags=["Timeseries"])


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def _resample_series(
    rows: List[Dict[str, Any]],
    freq: Literal["weekly", "monthly", "yearly"],
) -> List[Dict[str, Any]]:
    """
    rows: list of {"date": "YYYY-MM-DD", "cases": ..., "forecast": ..., "is_future"?: bool}
    freq: "weekly" | "monthly" | "yearly"
    Aggregates by sum. If 'is_future' exists, any future in the bucket → is_future=True.
    """
    if freq == "weekly":
        # Keep weekly as-is, preserving extra keys like is_future
        return sorted(rows, key=lambda r: r["date"])

    if not rows:
        return []

    df = pd.DataFrame(rows)

    if "date" not in df.columns:
        return []

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if df.empty:
        return []

    if freq == "monthly":
        rule = "MS"  # month start
    elif freq == "yearly":
        rule = "YS"  # year start
    else:
        return rows

    agg_dict: Dict[str, Any] = {
        "cases": ("cases", "sum"),
        "forecast": ("forecast", "sum"),
    }

    has_is_future = "is_future" in df.columns
    if has_is_future:
        agg_dict["is_future"] = ("is_future", "max")

    agg = df.groupby(pd.Grouper(key="date", freq=rule)).agg(**agg_dict).reset_index()

    result: List[Dict[str, Any]] = []
    for _, row in agg.iterrows():
        item: Dict[str, Any] = {
            "date": row["date"].strftime("%Y-%m-%d"),
            "cases": float(row["cases"]) if pd.notna(row["cases"]) else None,
            "forecast": float(row["forecast"]) if pd.notna(row["forecast"]) else None,
        }
        if has_is_future and "is_future" in row:
            val = row["is_future"]
            if pd.isna(val):
                item["is_future"] = False
            else:
                item["is_future"] = bool(val)
        result.append(item)

    return result


# ------------------------------------------------------------
# Main endpoint
# ------------------------------------------------------------

@router.get("/")
def get_timeseries(
    level: Literal["barangay", "city"] = Query("barangay"),
    name: Optional[str] = Query(None, description="Required when level=barangay"),
    freq: Literal["weekly", "monthly", "yearly"] = Query("weekly"),
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    horizon_type: Literal["test", "future"] = Query("future"),
):
    """
    Unified timeseries endpoint.

    - level=barangay, name="buhangin"
    - level=city
    """
    sb = get_supabase()

    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # --------------------------------------------------------
    # BARANGAY LEVEL
    # --------------------------------------------------------
    if level == "barangay":
        if not name:
            raise HTTPException(
                status_code=400,
                detail="name is required when level=barangay",
            )

        nm = normalize_name(name)

        weekly_resp = (
            sb.table("barangay_weekly")
            .select("week_start, cases")
            .eq("name", nm)
            .order("week_start")
            .execute()
        )
        weekly_rows = (
            sb.table("barangay_weekly_runs")
            .select("week_start, cases")
            .eq("run_id", rid)
            .eq("name", nm)
            .order("week_start")
            .execute()
            .data
        ) or []

        if not weekly_rows:
            weekly_rows = (
                sb.table("barangay_weekly")
                .select("week_start, cases")
                .eq("name", nm)
                .order("week_start")
                .execute()
                .data
            ) or []

        fore_rows = (
            sb.table("barangay_forecasts_long")
            .select("week_start, yhat, yhat_lower, yhat_upper, horizon_type")
            .eq("run_id", rid)
            .eq("name", nm)
            .eq("model_name", model)
            .eq("horizon_type", horizon_type)
            .order("week_start")
            .execute()
            .data
        ) or []


        if not weekly_rows and not fore_rows:
            raise HTTPException(
                status_code=404,
                detail=f"No timeseries found for barangay '{name}' (normalized='{nm}')",
            )

        series_map: Dict[str, Dict[str, Any]] = {}

        # Historical cases
        for row in weekly_rows:
            d = row["week_start"]
            series_map.setdefault(
                d,
                {"date": d, "cases": None, "forecast": None, "is_future": False},
            )
            series_map[d]["cases"] = row.get("cases")

        # Forecast rows
        for row in fore_rows:
            d = row["week_start"]
            val = row.get("yhat")

            series_map.setdefault(
                d, {"date": d, "cases": None, "forecast": None, "is_future": (horizon_type == "future")}
            )

            if val is not None:
                series_map[d]["forecast"] = float(val)

            # If cases exist, it’s historical regardless
            if series_map[d].get("cases") is not None:
                series_map[d]["is_future"] = False
            else:
                series_map[d]["is_future"] = (horizon_type == "future")


        series = sorted(series_map.values(), key=lambda r: r["date"])
        series = _resample_series(series, freq=freq)

        return {
            "level": "barangay",
            "name": nm,
            "freq": freq,
            "n_points": len(series),
            "series": series,
            "run_id": rid,
            "model_name": model,
            "horizon_type": horizon_type,
        }

    # --------------------------------------------------------
    # CITY LEVEL
    # --------------------------------------------------------
    city_rows = (
        sb.table("city_weekly_runs")
        .select("week_start, city_cases")
        .eq("run_id", rid)
        .order("week_start")
        .execute()
        .data
    ) or []

    if not city_rows:
        city_rows = (
            sb.table("city_weekly")
            .select("week_start, city_cases")
            .order("week_start")
            .execute()
            .data
        ) or []

    if not city_rows:
        raise HTTPException(status_code=404, detail="No city_weekly data found")

    fore_rows = (
        sb.table("city_forecasts_long")
        .select("week_start, yhat, horizon_type")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", horizon_type)
        .order("week_start")
        .execute()
        .data
    ) or []

    # Map forecast by week
    city_fore_map: Dict[str, float] = {}
    for row in fore_rows:
        d = row["week_start"]
        val = row.get("yhat")
        if val is None:
            continue
        city_fore_map[d] = float(val)

    series_map: Dict[str, Dict[str, Any]] = {}
    for row in city_rows:
        d = row["week_start"]
        series_map.setdefault(
            d,
            {"date": d, "cases": None, "forecast": None, "is_future": False},
        )
        series_map[d]["cases"] = row.get("city_cases")
        series_map[d]["is_future"] = False  # historical week

    for d, total_fore in city_fore_map.items():
        series_map.setdefault(
            d,
            {"date": d, "cases": None, "forecast": None, "is_future": True},
        )
        series_map[d]["forecast"] = total_fore
        if series_map[d]["cases"] is not None:
            series_map[d]["is_future"] = False

    series = sorted(series_map.values(), key=lambda r: r["date"])

    # Extend up to latest forecast date
    if fore_rows:
        max_fore_date = max(row["week_start"] for row in fore_rows)
        cur = pd.to_datetime(series[-1]["date"])
        target = pd.to_datetime(max_fore_date)

        while cur < target:
            cur += pd.Timedelta(days=7)
            d = cur.strftime("%Y-%m-%d")
            series_map.setdefault(
                d,
                {"date": d, "cases": None, "forecast": None, "is_future": True},
            )

    series = sorted(series_map.values(), key=lambda r: r["date"])
    series = _resample_series(series, freq=freq)

    return {
        "level": "city",
        "name": None,
        "freq": freq,
        "n_points": len(series),
        "series": series,
        "run_id": rid,
        "model_name": model,
        "horizon_type": horizon_type,
    }