# api/forecast.py
from __future__ import annotations
import statistics
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, List, Optional, Literal
from datetime import date
from .supabase_client import get_supabase
from .utils import normalize_name
from .run_helpers import (
    resolve_run_id,
    resolve_model_name,
    DEFAULT_MODEL,
    available_models_for_run,
    resolve_disagg_scheme_for_run,
)
from .risk import risk_from_baseline_percentiles
from .risk import risk_from_baseline_percentiles_windowed
from .jenks import jenks_breaks_safe, jenks_class
router = APIRouter()

# ================================================================
# 🔧 HELPERS — LOAD WEEKLY HISTORY + COMPUTE THRESHOLDS
# ================================================================
PERIOD_WEEKS = {
    "1w": 1,
    "2w": 2,
    "1m": 4,
    "3m": 12,
    "6m": 26,
    "1y": 52,
}

def _load_population_map(sb) -> Dict[str, int]:
    rows = (sb.table("latest_barangay_population").select("name, population").execute().data) or []
    out: Dict[str, int] = {}
    for r in rows:
        if r.get("population") is None or not r.get("name"):
            continue
        out[normalize_name(r["name"])] = int(r["population"])
    return out


def _load_weekly_history(sb, run_id: str) -> Dict[str, List[int]]:
    resp = (
        sb.table("barangay_weekly_runs")
        .select("name, week_start, cases")
        .eq("run_id", run_id)
        .order("week_start")
        .execute()
    )
    rows = resp.data or []

    if not rows:
        resp = sb.table("barangay_weekly").select("name, week_start, cases").order("week_start").execute()
        rows = resp.data or []

    out: Dict[str, List[int]] = {}
    for row in rows:
        nm = normalize_name(row["name"])
        cases = int(row.get("cases") or 0)
        out.setdefault(nm, []).append(cases)
    return out


def _latest_future_per_barangay(sb, run_id: str, model: str) -> List[Dict[str, object]]:
    rows = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start, yhat, yhat_lower, yhat_upper")
        .eq("run_id", run_id)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
        .execute()
        .data
    ) or []

    latest_by_name: Dict[str, Dict[str, object]] = {}
    for row in rows:
        nm = normalize_name(row["name"])
        if nm in latest_by_name:
            continue
        latest_by_name[nm] = {
            "name": nm,
            "week_start": row["week_start"],
            "yhat": row.get("yhat"),
            "yhat_lower": row.get("yhat_lower"),
            "yhat_upper": row.get("yhat_upper"),
        }

    if not latest_by_name:
        return []

    return [latest_by_name[k] for k in sorted(latest_by_name.keys())]


@router.get("/runs")
def list_runs(limit: int = 50):
    sb = get_supabase()
    rows = (
        sb.table("runs")
        .select("run_id, created_at, mode, run_kind, status, train_end, horizon_weeks, started_at, finished_at, error_message")
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
    models = available_models_for_run(sb, rid)
    default = DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else None)

    def _fetch_all(table: str) -> list[dict]:
        out = []
        start = 0
        page_size = 1000
        while True:
            chunk = (
                sb.table(table)
                .select("model_name")
                .eq("run_id", rid)
                .eq("horizon_type", "future")
                .range(start, start + page_size - 1)
                .execute()
                .data
            ) or []
            out.extend(chunk)
            if len(chunk) < page_size:
                break
            start += page_size
        return out

    city_rows = _fetch_all("city_forecasts_long")
    brgy_rows = _fetch_all("barangay_forecasts_long")

    city_counts: Dict[str, int] = {}
    for r in city_rows:
        m = str(r.get("model_name") or "").strip()
        if not m:
            continue
        city_counts[m] = city_counts.get(m, 0) + 1

    barangay_counts: Dict[str, int] = {}
    for r in brgy_rows:
        m = str(r.get("model_name") or "").strip()
        if not m:
            continue
        barangay_counts[m] = barangay_counts.get(m, 0) + 1

    return {
        "run_id": rid,
        "models": models,
        "default_model": default,
        "city_model_counts": city_counts,
        "barangay_model_counts": barangay_counts,
    }

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
def get_city_actual(run_id: Optional[str] = Query(None)):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)

    resp = (
        sb.table("city_weekly_runs")
        .select("run_id, week_start, city_cases")
        .eq("run_id", rid)
        .order("week_start")
        .execute()
    )
    rows = resp.data or []

    # TEMP fallback
    if not rows:
        resp = (
            sb.table("city_weekly")
            .select("week_start, city_cases")
            .order("week_start")
            .execute()
        )
        rows = resp.data or []

    return {"run_id": rid, "series": rows}

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
    rows = _latest_future_per_barangay(sb, rid, model)
    return {"run_id": rid, "model_name": model, "horizon_type": "future", "latest": rows}




# ================================================================
# 🟩 5. LATEST city-level (unchanged)
# ================================================================
@router.get("/latest/city")
def get_latest_city_forecast(run_id: Optional[str] = Query(None)):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)

    resp = (
        sb.table("city_weekly_runs")
        .select("week_start, city_cases")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []

    # TEMP fallback
    if not rows:
        resp = (
            sb.table("city_weekly")
            .select("week_start, city_cases")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []

    return rows[0] if rows else None


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
    period: str = Query("1w"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)
    weeks_to_sum = PERIOD_WEEKS.get(period, 1)

    city_rows = (
        sb.table("city_weekly_runs")
        .select("week_start, city_cases")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    if not city_rows:
        city_rows = (
            sb.table("city_weekly")
            .select("week_start, city_cases")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
    data_last_updated = city_rows[0]["week_start"] if city_rows else None

    brg = (sb.table("barangays").select("name, display_name").execute().data) or []
    display_map = {
        normalize_name(b["name"]): (b.get("display_name") or b["name"])
        for b in brg
        if b.get("name")
    }

    history = _load_weekly_history(sb, rid)
    pop_map = _load_population_map(sb)

    # Pull *future forecasts* for next N weeks for each barangay (period-aware)
    # NOTE: this avoids relying on "latest_barangay_forecast" which is 1-week only.
    frows = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start, yhat, yhat_lower, yhat_upper")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
        .execute()
        .data
    ) or []

    grouped: Dict[str, List[dict]] = {}
    for r in frows:
        nm = normalize_name(r["name"])
        grouped.setdefault(nm, []).append(r)

    barangay_latest = []
    total = 0.0

    rows_tmp = []      # store per-barangay computed values for a second pass
    case_values = []   # for Jenks on forecast_cases over period
    inc_values = []    # for Jenks on incidence per 100k over period

    for nm, rows in grouped.items():
        slice_rows = rows[:weeks_to_sum]

        total_fc = sum(float(x.get("yhat") or 0.0) for x in slice_rows)
        total += total_fc

        week_start = slice_rows[0]["week_start"] if slice_rows else None

        pop = pop_map.get(nm)
        inc = None
        if pop and pop > 0:
            inc = (float(total_fc) / float(pop)) * 100000.0

        # bounds (optional)
        yhat_lower = (
            sum(float(x.get("yhat_lower") or 0.0) for x in slice_rows)
            if any(x.get("yhat_lower") is not None for x in slice_rows)
            else None
        )
        yhat_upper = (
            sum(float(x.get("yhat_upper") or 0.0) for x in slice_rows)
            if any(x.get("yhat_upper") is not None for x in slice_rows)
            else None
        )

        history_len = len(history.get(nm, []))

        rows_tmp.append((nm, week_start, total_fc, inc, pop, history_len, yhat_lower, yhat_upper))

        case_values.append(float(total_fc))
        if inc is not None:
            inc_values.append(float(inc))

    # ✅ compute Jenks breaks AFTER we have all values
    case_breaks = jenks_breaks_safe(case_values, n_classes=5)
    inc_breaks = jenks_breaks_safe(inc_values, n_classes=5)

    # ✅ second pass: assign classes + build response rows
    for (nm, week_start, total_fc, inc, pop, history_len, yhat_lower, yhat_upper) in rows_tmp:
        cases_class = jenks_class(float(total_fc), case_breaks) if total_fc is not None else "unknown"
        burden_class = jenks_class(float(inc), inc_breaks) if inc is not None else "unknown"

        barangay_latest.append( 
            {
                "name": nm,
                "display_name": display_map.get(nm, nm),
                "week_start": week_start,
                "period": period,
                "weeks_to_sum": weeks_to_sum,
                "history_len": history_len,

                "forecast": float(total_fc),
                "forecast_cases": float(total_fc),
                "forecast_incidence_per_100k": inc,

                # ✅ Jenks classes
                "cases_class": cases_class,
                "burden_class": burden_class,

                # ✅ keep legacy keys (but now consistent with Jenks)
                "risk_level": burden_class,              # burden everywhere
                "risk_level_cases": cases_class,
                "risk_level_incidence": burden_class,

                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )
    return {
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
        "disagg_scheme": resolve_disagg_scheme_for_run(sb, rid),
        "period": period,
        "weeks_to_sum": weeks_to_sum,
        "city_latest": city_rows[0] if city_rows else None,
        "barangay_latest": barangay_latest,
        "total_forecasted_cases": round(total, 2),
        "data_last_updated": data_last_updated,
        "jenks_breaks_incidence": inc_breaks,
        "jenks_breaks_cases": case_breaks,
    }
