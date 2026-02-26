# api/forecast_rankings.py
from fastapi import APIRouter, Query
from datetime import datetime, date
from .supabase_client import get_supabase
from .utils import normalize_name
from .forecast import (
    _load_weekly_history,
)
from typing import Optional
from .run_helpers import resolve_run_id, resolve_model_name
from .forecast import _load_population_map
from .jenks import jenks_breaks_safe, jenks_class

router = APIRouter()

PERIOD_WEEKS = {
    "1w": 1,
    "2w": 2,
    "1m": 4,
    "3m": 12,
    "6m": 26,
    "1y": 52,
}

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
            latest_dt = datetime.fromisoformat(ws)
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
):
    sb = get_supabase()
    weeks_to_sum = PERIOD_WEEKS.get(period, 4)

    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    latest = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    latest_week_date = latest[0]["week_start"] if latest else None

    if not latest_week_date:
        legacy = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
        latest_week_date = legacy[0]["week_start"] if legacy else None

    history = _load_weekly_history(sb, rid)
    pop_map = _load_population_map(sb)

    brg = (sb.table("barangays").select("name, display_name").execute().data) or []
    display_map = {
        normalize_name(b["name"]): (b.get("display_name") or b["name"])
        for b in brg
        if b.get("name")
    }

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

    weekly_q = (
        sb.table("barangay_weekly_runs")
        .select("name, cases, week_start")
        .eq("run_id", rid)
        .order("name")
        .order("week_start", desc=True)
    )
    weekly_rows_raw = fetch_all(weekly_q)

    if not weekly_rows_raw:
        weekly_q = (
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .order("name")
            .order("week_start", desc=True)
        )
        weekly_rows_raw = fetch_all(weekly_q)

    grouped_weekly = {}
    for row in weekly_rows_raw:
        nm = normalize_name(row["name"])
        grouped_weekly.setdefault(nm, [])
        if len(grouped_weekly[nm]) < 2:
            grouped_weekly[nm].append(row)

    last_forecasts_q = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start, yhat")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start", desc=True)
    )
    last_forecasts = fetch_all(last_forecasts_q)

    grouped_last_fore = {}
    for row in last_forecasts:
        nm = normalize_name(row["name"])
        grouped_last_fore.setdefault(nm, [])
        if len(grouped_last_fore[nm]) < 2:
            grouped_last_fore[nm].insert(
                0, {"forecast": float(row.get("yhat") or 0.0), "is_future": True}
            )

    # -----------------------------
    # 1) First pass: compute values
    # -----------------------------
    rows_tmp = []
    case_values = []
    inc_values = []

    for name, future_rows in grouped_future.items():
        total_forecast = sum(float(r.get("yhat") or 0.0) for r in future_rows[:weeks_to_sum])

        # trend logic stays as-is
        weekly = grouped_weekly.get(name, [])
        last2_fore = grouped_last_fore.get(name, [])
        trend, last_week, this_week, trend_source, trend_message = compute_hybrid_trend(weekly, last2_fore)

        pop = pop_map.get(name)
        inc = None
        if pop and pop > 0:
            inc = (float(total_forecast) / float(pop)) * 100000.0

        rows_tmp.append((name, total_forecast, inc, trend, last_week, this_week, trend_source, trend_message))

        case_values.append(float(total_forecast))
        if inc is not None:
            inc_values.append(float(inc))

    # -----------------------------
    # 2) Compute Jenks breaks
    # -----------------------------
    case_breaks = jenks_breaks_safe(case_values, n_classes=5)
    inc_breaks = jenks_breaks_safe(inc_values, n_classes=5)

    # -----------------------------
    # 3) Second pass: assign classes
    # -----------------------------
    results = []
    for (name, total_forecast, inc, trend, last_week, this_week, trend_source, trend_message) in rows_tmp:
        cases_class = jenks_class(float(total_forecast), case_breaks) if total_forecast is not None else "unknown"
        burden_class = jenks_class(float(inc), inc_breaks) if inc is not None else "unknown"

        results.append(
            {
                "name": name,
                "pretty_name": display_map.get(name, name),

                # keep these numeric fields
                "total_forecast": round(total_forecast, 2),
                "total_forecast_cases": round(total_forecast, 2),
                "total_forecast_incidence_per_100k": inc,

                # ✅ Jenks labels (consistent with map + summary)
                "cases_class": cases_class,
                "burden_class": burden_class,

                # keep frontend legacy keys (now Jenks-based)
                "risk_level": burden_class,              # burden everywhere
                "risk_level_cases": cases_class,
                "risk_level_incidence": burden_class,

                # trend
                "trend": trend,
                "trend_source": trend_source,
                "last_week": last_week,
                "this_week": this_week,
                "trend_message": trend_message,
            }
        )

    # ✅ sort by burden incidence (you already want burden consistency)
    results.sort(key=lambda x: (x["total_forecast_incidence_per_100k"] or 0.0), reverse=True)

    return {
        "period": period,
        "weeks_to_sum": weeks_to_sum,
        "data_last_updated": latest_week_date,
        "model_current_date": latest_week_date,
        "user_current_date": str(date.today()),
        "rankings": results,
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",

        # optional: expose ranges so rankings UI can show legend too
        "jenks_breaks_incidence": inc_breaks,
        "jenks_breaks_cases": case_breaks,
    }