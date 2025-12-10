# api/forecast_rankings.py
from fastapi import APIRouter, Query
from datetime import datetime, date
from .supabase_client import get_supabase
from .utils import normalize_name
from .forecast import (
    _load_weekly_history,
    _compute_thresholds,
    _classify_risk,
)

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
def get_forecast_rankings(period: str = Query("1m")):
    sb = get_supabase()

    weeks_to_sum = PERIOD_WEEKS.get(period, 4)

    # =======================================================
    # 0️⃣ Load thresholds once for ALL barangays
    # =======================================================
    history = _load_weekly_history(sb)
    thresholds = _compute_thresholds(history)

    # =======================================================
    # 1️⃣ Fetch ALL future forecast rows (for horizon sums)
    # =======================================================
    forecasts = (
        sb.table("barangay_forecasts")
        .select("*")
        .eq("is_future", True)
        .order("week_start")
        .execute()
        .data
    )

    grouped_future = {}
    for row in forecasts:
        nm = normalize_name(row["name"])
        grouped_future.setdefault(nm, []).append(row)

    # =======================================================
    # 2️⃣ Fetch ALL weekly rows (for trends + data_last_updated)
    # =======================================================
    weekly_rows_raw = (
        sb.table("barangay_weekly")
        .select("name, cases, week_start")
        .order("name, week_start", desc=True)
        .execute()
        .data
    )

    grouped_weekly = {}
    latest_week_date = None

    for row in weekly_rows_raw:
        nm = normalize_name(row["name"])
        grouped_weekly.setdefault(nm, [])
        # keep up to 2 latest rows per barangay
        if len(grouped_weekly[nm]) < 2:
            grouped_weekly[nm].append(row)

        # track global latest week_start for disclaimer
        ws = row["week_start"]
        if latest_week_date is None or ws > latest_week_date:
            latest_week_date = ws

    # =======================================================
    # 3️⃣ Fetch ALL last 2 forecast rows per barangay (for fallback trend)
    # =======================================================
    last_forecasts = (
        sb.table("barangay_forecasts")
        .select("name, final_forecast, is_future, week_start")
        .order("name, week_start", desc=True)
        .execute()
        .data
    )

    grouped_last_fore = {}
    for row in last_forecasts:
        nm = normalize_name(row["name"])
        grouped_last_fore.setdefault(nm, [])

        # Insert at position 0 so the list becomes [older, newer]
        if len(grouped_last_fore[nm]) < 2:
            grouped_last_fore[nm].insert(
                0,
                {
                    "forecast": row["final_forecast"],
                    "is_future": row["is_future"],
                },
            )

    # =======================================================
    # 4️⃣ Compute rankings per barangay
    # =======================================================
    results = []

    for name, future_rows in grouped_future.items():
        # 4.1 Future horizon sum for the selected period
        total_forecast = sum(
            float(r["final_forecast"]) for r in future_rows[:weeks_to_sum]
        )

        # 4.2 Trend calculation
        weekly = grouped_weekly.get(name, [])
        last2_fore = grouped_last_fore.get(name, [])
        trend, last_week, this_week, trend_source, trend_message = compute_hybrid_trend(
            weekly, last2_fore
        )

        # 4.3 Risk level using SAME thresholds as /forecast/summary
        th = thresholds.get(name, {})
        risk = _classify_risk(total_forecast, th)

        results.append(
            {
                "name": name,
                "pretty_name": name.replace("-", " ").title(),
                "total_forecast": round(total_forecast, 2),
                "risk_level": risk,
                "trend": trend,
                "trend_source": trend_source,
                "last_week": last_week,
                "this_week": this_week,
                "trend_message": trend_message,
            }
        )

    # Sort by descending forecast
    results.sort(key=lambda x: x["total_forecast"], reverse=True)

    return {
        "period": period,
        "model_current_date": latest_week_date,        # <-- NEW
        "user_current_date": str(date.today()),        # <-- NEW
        "data_last_updated": latest_week_date,
        "rankings": results,
    }

