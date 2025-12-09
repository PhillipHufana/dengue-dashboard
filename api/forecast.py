# api/forecast.py
from __future__ import annotations

from fastapi import APIRouter
from .supabase_client import get_supabase
from .utils import normalize_name

import statistics
from typing import Dict, Any, List, Optional

router = APIRouter()

# ================================================================
# 🔧 HELPERS — LOAD WEEKLY HISTORY + COMPUTE THRESHOLDS
# ================================================================


def _load_weekly_history(sb) -> Dict[str, List[int]]:
    """
    Loads full historical dengue cases per barangay.

    Returns:
      {
        "acacia": [0, 1, 0, 2, 3, ...],
        "buhangin": [...],
      }
    """
    resp = (
        sb.table("barangay_weekly")
        .select("name, week_start, cases")
        .order("week_start")
        .execute()
    )

    rows = resp.data or []
    out: Dict[str, List[int]] = {}

    for row in rows:
        nm = normalize_name(row["name"])
        cases = int(row.get("cases") or 0)
        out.setdefault(nm, []).append(cases)

    return out


def _compute_thresholds(history: Dict[str, List[int]]) -> Dict[str, Dict[str, float]]:
    """
    For each barangay, compute:
      - alert    = mean + 2σ
      - epidemic = mean + 3σ
      - critical = 2 × epidemic

    This works for now on raw case counts.
    Later, when population is added, we switch to incidence rate.
    """
    out: Dict[str, Dict[str, float]] = {}

    for nm, series in history.items():
        if len(series) == 0:
            out[nm] = {"alert": 0, "epidemic": 0, "critical": 0}
            continue

        mean_val = statistics.mean(series)
        std_val = statistics.pstdev(series) if len(series) > 1 else 0

        alert = mean_val + 2 * std_val
        epidemic = mean_val + 3 * std_val
        critical = 2 * epidemic

        out[nm] = {
            "alert": alert,
            "epidemic": epidemic,
            "critical": critical,
        }

    return out


def _classify_risk(forecast: Optional[float], th: Dict[str, float]) -> str:
    """
    Map forecast value to a risk category based on thresholds.
    """
    if forecast is None:
        return "unknown"

    f = float(forecast)

    alert = th.get("alert")
    epidemic = th.get("epidemic")
    critical = th.get("critical")

    if alert is None:
        return "unknown"

    if f < alert:
        return "low"
    if f < epidemic:
        return "medium"
    if f < critical:
        return "high"
    return "critical"


# ================================================================
# 🟦 1. Barangay-level FORECAST TIMESERIES (unchanged)
# ================================================================
@router.get("/barangay/{name}")
def get_barangay_forecast(name: str):
    sb = get_supabase()
    nm = normalize_name(name)

    resp = (
        sb.table("barangay_forecasts")
        .select("*")
        .eq("name", nm)
        .order("week_start")
        .execute()
    )

    return {
        "barangay": nm,
        "series": resp.data or [],
    }


# ================================================================
# 🟦 2. City-level (unchanged)
# ================================================================
@router.get("/city")
def get_city_forecast():
    sb = get_supabase()
    resp = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start")
        .execute()
    )
    return resp.data or []


# ================================================================
# 🟦 3. Last N weeks (unchanged)
# ================================================================
@router.get("/weeks/{n}")
def get_recent_weeks(n: int):
    sb = get_supabase()

    city = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(n)
        .execute()
    ).data or []

    barangays = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .limit(n * 200)
        .execute()
    ).data or []

    return {
        "city": list(reversed(city)),
        "barangays": barangays,
    }


# ================================================================
# 🟩 4. LATEST forecast per barangay — WITH RISK
# ================================================================
@router.get("/latest/barangay")
def get_latest_forecast_for_all_barangays():
    sb = get_supabase()

    # Load historical weekly cases → thresholds
    history = _load_weekly_history(sb)
    thresholds = _compute_thresholds(history)

    # Load forecasts
    resp = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .execute()
    )

    rows = resp.data or []
    seen = set()
    out = []

    for row in rows:
        nm = normalize_name(row["name"])
        if nm in seen:
            continue

        seen.add(nm)

        forecast = row.get("final_forecast")
        risk = _classify_risk(forecast, thresholds.get(nm, {}))

        out.append(
            {
                "name": nm,
                "latest_forecast": forecast,
                "week_start": row["week_start"],
                "is_future": row["is_future"],
                "risk_level": risk,
                "thresholds": thresholds.get(nm),
            }
        )

    return out


# ================================================================
# 🟩 5. LATEST city-level (unchanged)
# ================================================================
@router.get("/latest/city")
def get_latest_city_forecast():
    sb = get_supabase()

    resp = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
    )

    return resp.data[0] if resp.data else None


@router.get("/summary")
def get_forecast_summary():
    sb = get_supabase()

    # Latest city (used for data_last_updated)
    city = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
    ).data

    data_last_updated = city[0]["week_start"] if city else None

    # Load thresholds + full historical weekly data
    history = _load_weekly_history(sb)
    thresholds = _compute_thresholds(history)

    # Load ALL forecasts
    resp = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    seen = set()
    barangay_latest = []
    total_forecast = 0.0

    for row in resp:
        nm = normalize_name(row["name"])
        if nm in seen:
            continue

        seen.add(nm)

        fc = float(row.get("final_forecast") or 0.0)
        total_forecast += fc

        risk = _classify_risk(fc, thresholds.get(nm, {}))

        # Trend using historical cases (last 2 points)
        hist_series = history.get(nm, [])

        trend = 0.0
        last_week = None
        this_week = None

        if len(hist_series) >= 2:
            last_week = hist_series[-2]
            this_week = hist_series[-1]

            if last_week > 0:
                trend = ((this_week - last_week) / last_week) * 100
            else:
                trend = 0.0

        barangay_latest.append(
            {
                "name": nm,
                "forecast": fc,
                "week_start": row["week_start"],
                "risk_level": risk,
                "trend": trend,
                "last_week": last_week,
                "this_week": this_week,
            }
        )

    return {
        "city_latest": city[0] if city else None,
        "barangay_latest": barangay_latest,
        "total_forecasted_cases": round(total_forecast, 2),
        "data_last_updated": data_last_updated,
    }
