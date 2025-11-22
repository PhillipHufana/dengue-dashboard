# api/forecast.py
from __future__ import annotations

from fastapi import APIRouter
from .supabase_client import get_supabase
from .utils import normalize_name

router = APIRouter()


# ----------------------------------------------------------
# 🟦 1. Barangay-level forecast (historical + future)
# ----------------------------------------------------------
@router.get("/barangay/{name}")
def get_barangay_forecast(name: str):
    """Return full time series for one barangay (actual + forecast)."""
    sb = get_supabase()
    nm = normalize_name(name)

    response = (
        sb.table("barangay_forecasts")
        .select("*")
        .eq("name", nm)
        .order("week_start")
        .execute()
    )

    return {
        "barangay": nm,
        "series": response.data or []
    }


# ----------------------------------------------------------
# 🟦 2. City-level forecast (historical + future)
# ----------------------------------------------------------
@router.get("/city")
def get_city_forecast():
    """Return full city-level weekly case series (actual + forecast)."""
    sb = get_supabase()

    response = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start")
        .execute()
    )

    return response.data or []


# ----------------------------------------------------------
# 🟦 3. Last N weeks (for mini dashboards)
# ----------------------------------------------------------
@router.get("/weeks/{n}")
def get_recent_weeks(n: int):
    """Return last N weeks of city cases + barangay forecasts."""
    sb = get_supabase()

    # CITY
    city_rows = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(n)
        .execute()
    ).data or []

    # BARANGAYS
    # 182 barangays → n * 182 rows
    bgy_rows = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .limit(n * 200)  # safe buffer
        .execute()
    ).data or []

    return {
        "city": list(reversed(city_rows)),
        "barangays": bgy_rows,
    }


# ----------------------------------------------------------
# 🟩 4. LATEST forecast per barangay (for choropleth)
# ----------------------------------------------------------
@router.get("/latest/barangay")
def get_latest_forecast_for_all_barangays():
    """
    Returns:
    [
      {
        "name": "acacia",
        "latest_forecast": 12.5,
        "week_start": "2025-01-06",
        "is_future": true
      },
      ...
    ]
    """
    sb = get_supabase()

    response = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .execute()
    )

    rows = response.data or []
    seen = set()
    latest = []

    for row in rows:
        nm = normalize_name(row["name"])
        if nm not in seen:
            seen.add(nm)
            latest.append({
                "name": nm,
                "latest_forecast": row["final_forecast"],
                "week_start": row["week_start"],
                "is_future": row["is_future"],
            })

    return latest


# ----------------------------------------------------------
# 🟩 5. LATEST city-level (for dashboard header)
# ----------------------------------------------------------
@router.get("/latest/city")
def get_latest_city_forecast():
    sb = get_supabase()

    response = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


# ----------------------------------------------------------
# 🟦 6. Summary card (for dashboard widgets)
# ----------------------------------------------------------
@router.get("/summary")
def get_forecast_summary():
    """
    Returns:
    {
      "city_latest": {...},
      "barangay_latest": [...],
      "total_forecasted_cases": float
    }
    """
    sb = get_supabase()

    # Latest city
    city = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
    ).data

    # Latest barangay forecasts
    rows = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    seen = set()
    barangay_latest = []
    total_forecast = 0

    for row in rows:
        nm = normalize_name(row["name"])
        if nm not in seen:
            seen.add(nm)
            total_forecast += row["final_forecast"] or 0
            barangay_latest.append({
                "name": nm,
                "forecast": row["final_forecast"],
                "week_start": row["week_start"],
            })

    return {
        "city_latest": city[0] if city else None,
        "barangay_latest": barangay_latest,
        "total_forecasted_cases": round(total_forecast, 2)
    }
