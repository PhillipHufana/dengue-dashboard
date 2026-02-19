# api/forecast.py
from __future__ import annotations
import statistics
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, List, Optional, Literal
from datetime import date
from .supabase_client import get_supabase
from .utils import normalize_name
from .run_helpers import resolve_run_id, resolve_model_name, DEFAULT_MODEL
from .risk import risk_from_baseline_percentiles

router = APIRouter()

# ================================================================
# 🔧 HELPERS — LOAD WEEKLY HISTORY + COMPUTE THRESHOLDS
# ================================================================

def _load_population_map(sb) -> Dict[str, int]:
    rows = (
        sb.table("latest_barangay_population")
        .select("name, population")
        .execute()
        .data
    ) or []
    return {r["name"]: int(r["population"]) for r in rows if r.get("population") is not None}

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


@router.get("/runs")
def list_runs(limit: int = 50):
    sb = get_supabase()
    rows = (
        sb.table("runs")
        .select("run_id, created_at, mode, train_end, horizon_weeks")
        .order("created_at", desc=True)
        .order("run_id", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []
    return {"runs": rows}

@router.get("/models")
def list_models(run_id: Optional[str] = Query(None)):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)

    # Use city_forecasts_long to avoid scanning huge barangay_forecasts_long
    rows = (
        sb.table("city_forecasts_long")
        .select("model_name")
        .eq("run_id", rid)
        .execute()
        .data
    ) or []
    models = sorted({r["model_name"] for r in rows if r.get("model_name")})
    default = DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else None)
    return {"run_id": rid, "models": models, "default_model": default}

# ================================================================
# 🟦 1. Barangay-level FORECAST TIMESERIES (unchanged)
# ================================================================
@router.get("/barangay/{name}")
def get_barangay_forecast(
    name: str,
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    horizon_type: Literal["test", "future"] = Query("future"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)
    nm = normalize_name(name)

    rows = (
        sb.table("barangay_forecasts_long")
        .select(
            "run_id, name, week_start, model_name, horizon_type, yhat, yhat_lower, yhat_upper"
        )
        .eq("run_id", rid)
        .eq("name", nm)
        .eq("model_name", model)
        .eq("horizon_type", horizon_type)
        .order("week_start")
        .execute()
        .data
    ) or []

    if not rows:
        raise HTTPException(status_code=404, detail="No forecast series found")

    return {
        "run_id": rid,
        "model_name": model,
        "horizon_type": horizon_type,
        "barangay": nm,
        "series": rows,
    }



# ================================================================
# 🟦 2. City-level (unchanged)
# ================================================================
@router.get("/city")
def get_city_actual():
    sb = get_supabase()
    resp = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start")
        .execute()
    )
    return resp.data or []

@router.get("/city/forecast")
def get_city_forecast_series(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    horizon_type: Literal["test", "future"] = Query("future"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    rows = (
        sb.table("city_forecasts_long")
        .select("run_id, week_start, model_name, horizon_type, yhat, yhat_lower, yhat_upper")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", horizon_type)
        .order("week_start")
        .execute()
        .data
    ) or []

    return {
        "run_id": rid,
        "model_name": model,
        "horizon_type": horizon_type,
        "series": rows,
    }



# ================================================================
# 🟩 4. LATEST forecast per barangay — WITH RISK
# ================================================================
@router.get("/latest/barangay")
def get_latest_future_forecast_for_all_barangays(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    rows = (
        sb.table("latest_barangay_forecast")
        .select("name, week_start, yhat, yhat_lower, yhat_upper")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
        .data
    ) or []
    return {"run_id": rid, "model_name": model, "horizon_type": "future", "latest": rows}




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


def _risk_from_forecast_simple(f: float) -> str:
    # Keep your existing simple thresholds for now
    if f < 5:
        return "low"
    if f < 15:
        return "medium"
    if f < 30:
        return "high"
    return "critical"

@router.get("/summary")
def get_forecast_summary(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # Latest city observed (for data_last_updated)
    city_rows = (
        sb.table("city_weekly")
        .select("*")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    data_last_updated = city_rows[0]["week_start"] if city_rows else None

    # Preload barangay display names (canonical -> display)
    brg = (sb.table("barangays").select("name, display_name").execute().data) or []
    display_map = {
        (b["name"]): (b.get("display_name") or b["name"])
        for b in brg
        if b.get("name")
    }

    # Thresholds for risk classification

    history = _load_weekly_history(sb)
    pop_map = _load_population_map(sb)

    # ✅ Use the view: already one latest row per barangay
    latest_rows = (
        sb.table("latest_barangay_forecast")
        .select("name, week_start, yhat, yhat_lower, yhat_upper")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
        .data
    ) or []

    barangay_latest = []
    total = 0.0

    for r in latest_rows:
        nm = r["name"]  # canonical
        fc = float(r.get("yhat") or 0.0)
        total += fc

        series = history.get(nm, [])
        pop = pop_map.get(nm)

        risk_pack = risk_from_baseline_percentiles(
            forecast_cases=fc,
            history_cases=series,
            population=pop,
        )

        barangay_latest.append({
            "name": nm,
            "display_name": display_map.get(nm, nm),
            "week_start": r["week_start"],

            # ✅ legacy
            "forecast": fc,
            "risk_level": risk_pack["risk_level_cases"],

            # ✅ new
            "forecast_cases": fc,
            "forecast_incidence_per_100k": risk_pack["forecast_incidence_per_100k"],
            "risk_level_cases": risk_pack["risk_level_cases"],
            "risk_level_incidence": risk_pack["risk_level_incidence"],

            "yhat_lower": r.get("yhat_lower"),
            "yhat_upper": r.get("yhat_upper"),
        })



    return {
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
        "city_latest": city_rows[0] if city_rows else None,
        "barangay_latest": barangay_latest,
        "total_forecasted_cases": round(total, 2),
        "data_last_updated": data_last_updated,
    }
