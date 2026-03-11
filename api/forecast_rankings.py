# api/forecast_rankings.py
from fastapi import APIRouter, Query
from datetime import datetime, date
from .supabase_client import get_supabase
from .utils import normalize_name
from typing import Optional
from .run_helpers import resolve_run_id, resolve_model_name
from .forecast import _load_population_map
from .jenks import jenks_breaks_safe, jenks_class
from cachetools import TTLCache

router = APIRouter()

PERIOD_WEEKS = {
    "1w": 1,
    "2w": 2,
    "1m": 4,
    "3m": 12,
    "6m": 26,
    "1y": 52,
}

RANKING_BASIS_SET = {"incidence", "cases", "surge"}
SURGE_FORECAST_WEEKS = 4
SURGE_HISTORY_WEEKS = 8
SURGE_EPSILON = 1.0

_rankings_cache = TTLCache(maxsize=64, ttl=300)  # 5 minute cache for rankings

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


def compute_hybrid_trend(weekly_rows, forecast_rows):
    latest_dt = None
    age_days = None

    if weekly_rows:
        ws = weekly_rows[0]["week_start"]
        if isinstance(ws, str):
            latest_dt = datetime.fromisoformat(ws.replace("Z", "+00:00"))
        else:
            latest_dt = datetime.combine(ws, datetime.min.time())
        age_days = (datetime.now().date() - latest_dt.date()).days

    if weekly_rows and len(weekly_rows) >= 2 and age_days is not None and age_days <= 45:
        last = weekly_rows[1]["cases"]
        curr = weekly_rows[0]["cases"]
        if last > 0:
            trend = ((curr - last) / last) * 100
        else:
            trend = 100 if curr > 0 else 0
        return (round(trend), last, curr, "historical", "Trend based on latest reported cases.")

    if len(forecast_rows) >= 2:
        last = float(forecast_rows[-2]["forecast"])
        curr = float(forecast_rows[-1]["forecast"])
        if last > 0:
            trend = ((curr - last) / last) * 100
        else:
            trend = 100 if curr > 0 else 0
        if age_days is not None:
            msg = f"Trend based on forecast (no new reported cases for {age_days} days)."
        else:
            msg = "Trend based on forecasted values."
        return round(trend), last, curr, "forecast", msg

    if age_days is not None and age_days > 45:
        msg = f"Trend unavailable (no recent data; last update {age_days} days ago)."
    else:
        msg = "Trend unavailable."
    return 0, None, None, "none", msg
@router.get("/rankings")
def get_forecast_rankings(
    period: str = Query("1m"),
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    ranking_basis: str = Query("incidence"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)
    weeks_to_sum = PERIOD_WEEKS.get(period, 4)
    basis = str(ranking_basis or "incidence").strip().lower()
    if basis not in RANKING_BASIS_SET:
        basis = "incidence"

    cache_key = (rid, model, period, basis)
    if cache_key in _rankings_cache:
        return _rankings_cache[cache_key]

    pop_map = _load_population_map(sb)

    brg = (sb.table("barangays").select("name, display_name").execute().data) or []
    display_map = {
        normalize_name(b["name"]): (b.get("display_name") or b["name"])
        for b in brg
        if b.get("name")
    }

    # forecasts (one query only)
    forecasts_q = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start, yhat")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
    )
    forecasts = fetch_all(forecasts_q)

    grouped_future = {}
    for row in forecasts:
        nm = normalize_name(row["name"])
        grouped_future.setdefault(nm, []).append(row)

    # --- Get latest two observed weeks (city-level calendar)
    city_weeks = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(max(2, SURGE_HISTORY_WEEKS))
        .execute()
        .data
    ) or []

    if not city_weeks:
        city_weeks = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(max(2, SURGE_HISTORY_WEEKS))
            .execute()
            .data
        ) or []

    latest_week_date = city_weeks[0]["week_start"] if len(city_weeks) >= 1 else None
    prev_week_date = city_weeks[1]["week_start"] if len(city_weeks) >= 2 else None

    weeks_for_trend = [w for w in [latest_week_date, prev_week_date] if w is not None]
    weeks_for_surge = [x.get("week_start") for x in city_weeks[:SURGE_HISTORY_WEEKS] if x.get("week_start") is not None]
    weeks_for_weekly = list(dict.fromkeys(weeks_for_trend + weeks_for_surge))

    # --- Fetch only barangay rows for trend + surge windows
    weekly_rows_raw = []
    if weeks_for_weekly:
        weekly_rows_raw = (
            sb.table("barangay_weekly_runs")
            .select("name, cases, week_start")
            .eq("run_id", rid)
            .in_("week_start", weeks_for_weekly)
            .execute()
            .data
        ) or []

    if not weekly_rows_raw and weeks_for_weekly:
        weekly_rows_raw = (
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .in_("week_start", weeks_for_weekly)
            .execute()
            .data
        ) or []

    # --- Build grouped_weekly with newest first
    grouped_weekly = {}
    for row in weekly_rows_raw:
        nm = normalize_name(row["name"])
        grouped_weekly.setdefault(nm, []).append(row)

    for nm in grouped_weekly:
        grouped_weekly[nm].sort(key=lambda r: r["week_start"], reverse=True)

    rows_tmp, case_values, inc_values = [], [], []

    for name, future_rows in grouped_future.items():
        total_forecast = sum(float(r.get("yhat") or 0.0) for r in future_rows[:weeks_to_sum])

        weekly = grouped_weekly.get(name, [])
        weekly_recent2 = weekly[:2]
        weekly_recent8 = weekly[:SURGE_HISTORY_WEEKS]
        last2_fore = [{"forecast": float(r.get("yhat") or 0.0)} for r in future_rows[-2:]] if len(future_rows) >= 2 else []
        trend, last_week, this_week, trend_source, trend_message = compute_hybrid_trend(weekly_recent2, last2_fore)

        pop = pop_map.get(name)
        inc = (float(total_forecast) / float(pop) * 100000.0) if pop and pop > 0 else None
        forecast_4w_cases = sum(float(r.get("yhat") or 0.0) for r in future_rows[:SURGE_FORECAST_WEEKS])
        past_8w_avg_cases = (
            sum(float(r.get("cases") or 0.0) for r in weekly_recent8) / float(SURGE_HISTORY_WEEKS)
            if weekly_recent8
            else 0.0
        )
        surge_score = forecast_4w_cases / (past_8w_avg_cases + SURGE_EPSILON)

        rows_tmp.append(
            (
                name,
                total_forecast,
                inc,
                trend,
                last_week,
                this_week,
                trend_source,
                trend_message,
                forecast_4w_cases,
                past_8w_avg_cases,
                surge_score,
            )
        )
        case_values.append(float(total_forecast))
        if inc is not None:
            inc_values.append(float(inc))

    case_breaks = jenks_breaks_safe(case_values, n_classes=5)
    inc_breaks = jenks_breaks_safe(inc_values, n_classes=5)

    results = []
    for (
        name,
        total_forecast,
        inc,
        trend,
        last_week,
        this_week,
        trend_source,
        trend_message,
        forecast_4w_cases,
        past_8w_avg_cases,
        surge_score,
    ) in rows_tmp:
        cases_class = jenks_class(float(total_forecast), case_breaks) if total_forecast is not None else "unknown"
        burden_class = jenks_class(float(inc), inc_breaks) if inc is not None else "unknown"

        results.append(
            {
                "name": name,
                "pretty_name": display_map.get(name, name),
                "total_forecast": round(total_forecast, 2),
                "total_forecast_cases": round(total_forecast, 2),
                "total_forecast_incidence_per_100k": inc,
                "cases_class": cases_class,
                "burden_class": burden_class,
                "risk_level": burden_class,
                "risk_level_cases": cases_class,
                "risk_level_incidence": burden_class,
                "trend": trend,
                "trend_source": trend_source,
                "last_week": last_week,
                "this_week": this_week,
                "trend_message": trend_message,
                "forecast_4w_cases": round(float(forecast_4w_cases), 4),
                "past_8w_avg_cases": round(float(past_8w_avg_cases), 4),
                "surge_score": round(float(surge_score), 6),
            }
        )

    if basis == "surge":
        results.sort(key=lambda x: float(x.get("surge_score") or 0.0), reverse=True)
    elif basis == "cases":
        results.sort(key=lambda x: float(x.get("total_forecast_cases") or 0.0), reverse=True)
    else:
        results.sort(key=lambda x: float(x.get("total_forecast_incidence_per_100k") or 0.0), reverse=True)

    resp = {
        "period": period,
        "weeks_to_sum": weeks_to_sum,
        "ranking_basis": basis,
        "data_last_updated": latest_week_date,
        "model_current_date": latest_week_date,
        "user_current_date": str(date.today()),
        "rankings": results,
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
        "jenks_breaks_incidence": inc_breaks,
        "jenks_breaks_cases": case_breaks,
    }

    _rankings_cache[cache_key] = resp
    return resp
