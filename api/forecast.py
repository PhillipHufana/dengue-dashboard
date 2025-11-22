# api/forecast.py
from fastapi import APIRouter
from .supabase_client import get_supabase
from .utils import normalize_name

router = APIRouter()


@router.get("/barangay/{name}")
def get_barangay_forecast(name: str):
    """Get all forecasts (historical + future) for one barangay."""
    sb = get_supabase()
    normalized = normalize_name(name)

    response = (
        sb.table("barangay_forecasts")
        .select("*")
        .eq("name", normalized)
        .order("week_start")
        .execute()
    )
    return {"barangay": name, "forecasts": response.data}


@router.get("/city")
def get_city_forecast():
    """Full city-level forecast series."""
    sb = get_supabase()
    response = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start")
        .execute()
    )
    return response.data


@router.get("/weeks/{n}")
def get_recent_n_weeks(n: int):
    """Return last N weeks of true cases and forecasts."""
    sb = get_supabase()

    city_rows = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(n)
        .execute()
    ).data

    forecast_rows = (
        sb.table("barangay_forecasts")
        .select("*")
        .order("week_start", desc=True)
        .limit(n * 182)
        .execute()
    ).data

    return {
        "city": city_rows[::-1],
        "barangays": forecast_rows,
    }
