# api/geo.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from .supabase_client import get_supabase
from typing import Optional, Dict, Any, List
import json
from .run_helpers import resolve_run_id, resolve_model_name
from .forecast import _load_population_map
from .utils import normalize_name
from typing import Sequence, Tuple
from .jenks import jenks_breaks_safe, jenks_class

router = APIRouter(prefix="/geo", tags=["geo"])

PERIOD_WEEKS = {
    "1w": 1,
    "2w": 2,
    "1m": 4,
    "3m": 12,
    "6m": 26,
    "1y": 52,
}
SURGE_HISTORY_WEEKS = 8
SURGE_EPSILON = 1.0

def fetch_all(q, page_size: int = 1000):
    out = []
    start = 0
    while True:
        chunk = q.range(start, start + page_size - 1).execute().data or []
        out.extend(chunk)
        if len(chunk) < page_size:
            break
        start += page_size
    return out


def _latest_future_per_barangay_from_long(sb, run_id: str, model: str) -> Dict[str, float]:
    frows = (
        sb.table("barangay_forecasts_long")
        .select("name, yhat")
        .eq("run_id", run_id)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
        .execute()
        .data
    ) or []

    latest = {}
    for row in frows:
        nm = normalize_name(row["name"])
        if nm not in latest:
            latest[nm] = float(row.get("yhat") or 0.0)
    return latest



@router.get("/choropleth")
def get_choropleth(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    period: str = Query("1w"),
    data_mode: str = Query("forecast"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)
    weeks_to_sum = PERIOD_WEEKS.get(period, 1)
    mode = str(data_mode or "forecast").strip().lower()
    if mode not in {"forecast", "observed"}:
        mode = "forecast"

    brg_rows = (
        sb.table("barangays")
        .select("name, display_name, geom_json")
        .execute()
        .data
    ) or []

    # Period-aware: fetch future forecast rows and sum first N weeks
    frows_q = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start, yhat")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
    )

    frows = fetch_all(frows_q)

    grouped: Dict[str, List[dict]] = {}
    for r in frows:
        nm = normalize_name(r["name"])
        grouped.setdefault(nm, []).append(r)

    pop_map = _load_population_map(sb)
    city_weeks = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(max(SURGE_HISTORY_WEEKS, weeks_to_sum))
        .execute()
        .data
    ) or []
    if not city_weeks:
        city_weeks = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(max(SURGE_HISTORY_WEEKS, weeks_to_sum))
            .execute()
            .data
        ) or []
    data_last_updated = city_weeks[0]["week_start"] if city_weeks else None
    weeks_for_surge = [x.get("week_start") for x in city_weeks[:SURGE_HISTORY_WEEKS] if x.get("week_start") is not None]
    weeks_for_observed = [x.get("week_start") for x in city_weeks[:weeks_to_sum] if x.get("week_start") is not None]
    weeks_for_needed = list(dict.fromkeys(weeks_for_surge + weeks_for_observed))
    weekly_rows = []
    if weeks_for_needed:
        weekly_rows = fetch_all(
            sb.table("barangay_weekly_runs")
            .select("name, week_start, cases")
            .eq("run_id", rid)
            .in_("week_start", weeks_for_needed)
        )
    if not weekly_rows and weeks_for_needed:
        weekly_rows = fetch_all(
            sb.table("barangay_weekly")
            .select("name, week_start, cases")
            .in_("week_start", weeks_for_needed)
        )
    weekly_lookup: Dict[str, Dict[str, float]] = {}
    for row in weekly_rows:
        nm = normalize_name(row["name"])
        ws = row.get("week_start")
        if not ws:
            continue
        weekly_lookup.setdefault(nm, {})[str(ws)] = float(row.get("cases") or 0.0)

    # ---- 1st pass: compute forecast sums + incidence per barangay
    rows_for_features = []  # temporary store
    case_values: List[float] = []
    inc_values: List[float] = []
    surge_values: List[float] = []

    # city-level aggregates (public-health correct)
    city_forecast_cases = 0.0
    city_baseline_expected_cases = 0.0
    city_population = 0
    for b in brg_rows:
        nm = normalize_name(b["name"])
        geom = b.get("geom_json")
        if not geom:
            continue

        rows = grouped.get(nm, [])
        slice_rows = rows[:weeks_to_sum]
        forecast_total = sum(float(x.get("yhat") or 0.0) for x in slice_rows) if slice_rows else 0.0
        wk0 = slice_rows[0]["week_start"] if slice_rows else None
        series = weekly_lookup.get(nm, {})
        observed_total = sum(float(series.get(str(ws), 0.0)) for ws in weeks_for_observed) if weeks_for_observed else 0.0
        total_fc = observed_total if mode == "observed" else forecast_total

        case_values.append(float(total_fc))
        city_forecast_cases += float(total_fc)

        pop = pop_map.get(nm)
        if pop and pop > 0:
            city_population += int(pop)

        recent = [float(series.get(str(ws), 0.0)) for ws in weeks_for_surge] if weeks_for_surge else []
        past_8w_avg = (sum(recent) / float(SURGE_HISTORY_WEEKS)) if recent else 0.0
        baseline_expected_w = float(past_8w_avg) * float(weeks_to_sum)
        surge_ratio = float(forecast_total) / float(baseline_expected_w + SURGE_EPSILON)

        inc = None
        if pop and pop > 0:
            # cumulative incidence per 100k over the selected period
            inc = (float(total_fc) / float(pop)) * 100000.0
        forecast_inc = (float(forecast_total) / float(pop) * 100000.0) if pop and pop > 0 else None
        observed_inc = (float(observed_total) / float(pop) * 100000.0) if pop and pop > 0 else None

        if inc is not None:
            inc_values.append(inc)
        if surge_ratio is not None:
            surge_values.append(float(surge_ratio))
        city_baseline_expected_cases += float(baseline_expected_w)

        rows_for_features.append(
            (
                b,
                nm,
                geom,
                total_fc,
                inc,
                surge_ratio,
                baseline_expected_w,
                wk0,
                pop,
                forecast_total,
                observed_total,
                forecast_inc,
                observed_inc,
            )
        )

    # ---- Compute Jenks breaks across incidence distribution
    # 5 classes = 6 breakpoints

    breaks = jenks_breaks_safe(inc_values, n_classes=5)
    case_breaks = jenks_breaks_safe(case_values, n_classes=5)
    surge_breaks = jenks_breaks_safe(surge_values, n_classes=5)

    # ---- 2nd pass: build GeoJSON features with Jenks class labels
    features = []
    for (
        b,
        nm,
        geom,
        total_fc,
        inc,
        surge_ratio,
        baseline_expected_w,
        wk0,
        pop,
        forecast_total,
        observed_total,
        forecast_inc,
        observed_inc,
    ) in rows_for_features:
        inc_class = jenks_class(inc, breaks)
        
        cases_class = jenks_class(total_fc, case_breaks) if total_fc is not None else "unknown"
        surge_class = jenks_class(surge_ratio, surge_breaks) if surge_ratio is not None else "unknown"

        properties = {
            "name": nm,
            "display_name": b.get("display_name") or nm,
            "period": period,
            "weeks_to_sum": weeks_to_sum,
            "period_start_week": wk0,

            "cases_class": cases_class,
            "risk_level_cases": cases_class,   # optional: keep frontend compatibility
            "risk_level": cases_class,         # optional legacy key

            # Keep forecast fields
            "latest_forecast": total_fc,
            "forecast_cases": total_fc,
            "forecast_incidence_per_100k": inc,
            "forecast_surge_ratio": surge_ratio,
            "baseline_expected_w": baseline_expected_w,
            "surge_class": surge_class,
            "observed_cases": observed_total,
            "observed_incidence_per_100k": observed_inc,
            "prophet_forecast_cases": None,
            "arima_forecast_cases": None,

            "population": pop,

            # NEW: choropleth burden classification
            "burden_class": inc_class,  # very_low..very_high

            # Keep existing keys so frontend won’t break
            # You can map these to your existing risk keys if you want:
            "risk_level_incidence": inc_class,

            "run_id": rid,
            "model_name": model,
            "horizon_type": "future",

            "latest_cases": 0,
            "latest_week": None,
        }

        features.append({"type": "Feature", "geometry": geom, "properties": properties})

    city_incidence_per_100k = (
        (city_forecast_cases / float(city_population)) * 100000.0
        if city_population > 0
        else None
    )
    city_surge_ratio = (
        float(city_forecast_cases) / float(city_baseline_expected_cases + SURGE_EPSILON)
        if city_forecast_cases is not None
        else None
    )

    return {
        "type": "FeatureCollection",
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
        "data_mode": mode,
        "period": period,
        "jenks_breaks_incidence": breaks,
        "jenks_breaks_cases": case_breaks,
        "jenks_breaks_surge": surge_breaks,
        "weeks_to_sum": weeks_to_sum,
        "baseline_weeks": SURGE_HISTORY_WEEKS,
        "surge_epsilon": SURGE_EPSILON,
        "data_last_updated": data_last_updated,

        # public-health KPIs (city-level)
        "city_forecast_cases": round(city_forecast_cases, 2),
        "city_population": city_population,
        "city_incidence_per_100k": round(city_incidence_per_100k, 2) if city_incidence_per_100k is not None else None,
        "city_baseline_expected_cases": round(city_baseline_expected_cases, 2),
        "city_surge_ratio": round(city_surge_ratio, 6) if city_surge_ratio is not None else None,

        "features": features,
    }

@router.get("/hotspots/top")
def dengue_hotspots_top(
    n: int = 10,
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # latest observed week_start (shared baseline)
    city = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []

    if not city:
        city = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
    latest_ws = city[0]["week_start"] if city else None
    if not latest_ws:
        return []
    weekly = (
        sb.table("barangay_weekly_runs")
        .select("name, cases, week_start")
        .eq("run_id", rid)
        .eq("week_start", latest_ws)
        .execute()
        .data
    ) or []

    if not weekly:
        weekly = (
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .eq("week_start", latest_ws)
            .execute()
            .data
        ) or []
    latest_cases = {r["name"]: int(r.get("cases") or 0) for r in weekly}

    latest_fc = _latest_future_per_barangay_from_long(sb, rid, model)

    all_brgy = set(latest_cases) | set(latest_fc)
    hotspots = []
    for nm in all_brgy:
        cases = latest_cases.get(nm, 0)
        forecast = latest_fc.get(nm, 0.0)
        growth = float(forecast) - float(cases)

        hotspots.append(
            {"name": nm, "latest_cases": cases, "latest_forecast": forecast, "growth": growth}
        )

    hotspots.sort(key=lambda x: x["growth"], reverse=True)
    return hotspots[:n]
