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
from .risk import risk_from_baseline_percentiles
from .forecast import _load_population_map


router = APIRouter()

# period → number of forecast weeks to sum
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
    """
    weekly_rows: [{"week_start": "...", "cases": n}, ...] (latest first)
    forecast_rows: [{"forecast": n, "is_future": bool}, ...] (oldest → newest)

    Returns:
      trend_percent,
      last_week_value,
      this_week_value,
      trend_source,   # "historical" | "forecast" | "none"
      trend_message   # human-readable explanation
    """
    latest_dt = None
    age_days = None

    if weekly_rows:
        latest_dt = datetime.fromisoformat(weekly_rows[0]["week_start"])
        age_days = (datetime.now().date() - latest_dt.date()).days

    # 1️⃣ Fresh historical data (≤ 45 days old) → use real cases
    if weekly_rows and len(weekly_rows) >= 2 and age_days is not None and age_days <= 45:
        last = weekly_rows[1]["cases"]
        curr = weekly_rows[0]["cases"]

        if last > 0:
            trend = ((curr - last) / last) * 100
        else:
            trend = 100 if curr > 0 else 0

        return (
            round(trend),
            last,
            curr,
            "historical",
            "Trend based on latest reported cases.",
        )

    # 2️⃣ Stale or missing historical → use forecast fallback when available
    if len(forecast_rows) >= 2:
        # forecast_rows is ordered oldest → newest
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

    # 3️⃣ No usable trend at all
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
    # model = resolve_model_name(sb, rid, model_name)
    model = model_name or "preferred"
    
    # ✅ Fast: latest observed week from run-scoped city weekly
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

    # TEMP fallback
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

    # Load once
    history = _load_weekly_history(sb, rid)
    pop_map = _load_population_map(sb)

    brg = (
        sb.table("barangays")
        .select("name, display_name")
        .execute()
        .data
    ) or []
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
        .order("week_start")  # ASC
    )
    forecasts = fetch_all(forecasts_q)


    grouped_future = {}
    for row in forecasts:
        nm = normalize_name(row["name"])
        grouped_future.setdefault(nm, []).append(row)

    print("forecast rows:", len(forecasts), "unique barangays:", len(grouped_future))

    weekly_q = (
        sb.table("barangay_weekly_runs")
        .select("name, cases, week_start")
        .eq("run_id", rid)
        .order("name")
        .order("week_start", desc=True)
    )
    weekly_rows_raw = fetch_all(weekly_q)

    # TEMP fallback
    if not weekly_rows_raw:
        weekly_q = (
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .order("name")
            .order("week_start", desc=True)
        )
        weekly_rows_raw = fetch_all(weekly_q)


    grouped_weekly = {}
    # latest_week_date = None

    for row in weekly_rows_raw:
        nm = normalize_name(row["name"])
        grouped_weekly.setdefault(nm, [])
        if len(grouped_weekly[nm]) < 2:
            grouped_weekly[nm].append(row)

        # ws = row.get("week_start")
        # if ws:
        #     if latest_week_date is None:
        #         latest_week_date = ws
        #     else:
        #         try:
        #             if datetime.fromisoformat(ws) > datetime.fromisoformat(latest_week_date):
        #                 latest_week_date = ws
        #         except Exception:
        #             if ws > latest_week_date:
        #                 latest_week_date = ws

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

    results = []
    for name, future_rows in grouped_future.items():
        total_forecast = sum(float(r.get("yhat") or 0.0) for r in future_rows[:weeks_to_sum])

        weekly = grouped_weekly.get(name, [])
        last2_fore = grouped_last_fore.get(name, [])
        trend, last_week, this_week, trend_source, trend_message = compute_hybrid_trend(
            weekly, last2_fore
        )

        series = history.get(name, [])
        pop = pop_map.get(name)

        risk_pack = risk_from_baseline_percentiles(
            forecast_cases=total_forecast,
            history_cases=series,
            population=pop,
        )

        # ✅ keep legacy keys for frontend
        results.append(
            {
                "name": name,
                "pretty_name": display_map.get(name, name),

                "total_forecast": round(total_forecast, 2),
                "risk_level": risk_pack["risk_level_cases"],

                # ✅ new richer fields
                "total_forecast_cases": round(total_forecast, 2),
                "total_forecast_incidence_per_100k": risk_pack["forecast_incidence_per_100k"],
                "risk_level_cases": risk_pack["risk_level_cases"],
                "risk_level_incidence": risk_pack["risk_level_incidence"],

                "trend": trend,
                "trend_source": trend_source,
                "last_week": last_week,
                "this_week": this_week,
                "trend_message": trend_message,
            }
        )

    results.sort(key=lambda x: x["total_forecast_cases"], reverse=True)



    return {
        "period": period,
        "data_last_updated": latest_week_date,
        "model_current_date": latest_week_date,  # ✅ add this because UI expects it
        "user_current_date": str(date.today()),
        "rankings": results,
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
    }

