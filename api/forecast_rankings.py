# api/forecast_rankings.py
from fastapi import APIRouter, Query
from datetime import datetime, date
from .supabase_client import get_supabase
from .utils import normalize_name
from typing import Optional, Any
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
DATA_MODE_SET = {"forecast", "observed"}
SURGE_HISTORY_WEEKS = 8
SURGE_FALLBACK_BASELINE_WEEKS = 26
SURGE_MIN_NONZERO_FOR_SHORT_BASELINE = 4
SURGE_EPSILON = 1.0
SURGE_MIN_FORECAST_CASES = 2.0
OBSERVED_INCIDENCE_TIEBREAK_MIN_CASES = 3.0
RANKING_FORMULA_VERSION = "v3_adaptive_baseline_8w_or_26w"

_rankings_cache = TTLCache(maxsize=64, ttl=300)  # 5 minute cache for rankings
_action_priority_cache = TTLCache(maxsize=64, ttl=300)

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


def _build_action_priority_rows(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    items = [dict(r) for r in rows]
    if mode == "observed":
        items.sort(
            key=lambda x: (
                float(x.get("observed_cases_w") or x.get("total_forecast_cases") or 0.0),
                float(x.get("observed_incidence_w") or x.get("total_forecast_incidence_per_100k") or 0.0)
                if float(x.get("observed_cases_w") or x.get("total_forecast_cases") or 0.0) >= OBSERVED_INCIDENCE_TIEBREAK_MIN_CASES
                else float("-inf"),
                str(x.get("name") or ""),
            ),
            reverse=True,
        )
        for i, r in enumerate(items, start=1):
            r["rank"] = int(i)
            r["queue_type"] = "respond_now"
            r["rank_reason"] = f"High recent observed burden (past W: {float(r.get('total_forecast_cases') or 0.0):.2f})"
    else:
        items.sort(
            key=lambda x: (
                1 if bool(x.get("priority_eligible")) else 0,
                float(x.get("surge_score") or 0.0),
                float(x.get("forecast_w_cases") or 0.0),
                str(x.get("name") or ""),
            ),
            reverse=True,
        )
        for i, r in enumerate(items, start=1):
            r["rank"] = int(i)
            r["queue_type"] = "prepare_next"
            r["rank_reason"] = (
                f"Surge {float(r.get('surge_score') or 0.0):.2f}x vs baseline; "
                f"forecast W: {float(r.get('forecast_w_cases') or 0.0):.2f}"
            )
    return items


def _recommended_class(row: dict[str, Any], mode: str) -> str:
    if mode == "observed":
        return str(row.get("cases_class") or row.get("risk_level_cases") or row.get("risk_level") or "unknown")
    return str(row.get("surge_class") or "unknown")


def _recommended_value(row: dict[str, Any], mode: str) -> float:
    if mode == "observed":
        return float(row.get("observed_cases_w") or row.get("total_forecast_cases") or row.get("total_forecast") or 0.0)
    return float(row.get("surge_score") or 0.0)


@router.get("/action-priority")
def get_action_priority(
    period: str = Query("1m"),
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    view_mode: str = Query("forecast"),
):
    mode = str(view_mode or "forecast").strip().lower()
    if mode not in DATA_MODE_SET:
        mode = "forecast"

    cache_key = (run_id, model_name, period, mode)
    if cache_key in _action_priority_cache:
        return _action_priority_cache[cache_key]

    if mode == "observed":
        base = get_forecast_rankings(
            period=period,
            run_id=run_id,
            model_name=model_name,
            ranking_basis="cases",
            data_mode="observed",
        )
    else:
        base = get_forecast_rankings(
            period=period,
            run_id=run_id,
            model_name=model_name,
            ranking_basis="surge",
            data_mode="forecast",
        )

    ranked = _build_action_priority_rows(list(base.get("rankings") or []), mode)
    top_row = ranked[0] if ranked else None
    resp = {
        "run_id": base.get("run_id"),
        "model_name": base.get("model_name"),
        "view_mode": mode,
        "queue_type": "respond_now" if mode == "observed" else "prepare_next",
        "period": base.get("period"),
        "weeks_to_sum": base.get("weeks_to_sum"),
        "baseline_weeks": base.get("baseline_weeks"),
        "baseline_fallback_weeks": base.get("baseline_fallback_weeks"),
        "baseline_min_nonzero_8w": base.get("baseline_min_nonzero_8w"),
        "surge_epsilon": base.get("surge_epsilon"),
        "surge_min_forecast_cases": base.get("surge_min_forecast_cases"),
        "ranking_formula_version": base.get("ranking_formula_version") or RANKING_FORMULA_VERSION,
        "data_last_updated": base.get("data_last_updated"),
        "model_current_date": base.get("model_current_date"),
        "user_current_date": base.get("user_current_date"),
        "period_start_week": base.get("period_start_week"),
        "period_end_week": base.get("period_end_week"),
        "recommended_metric": "cases" if mode == "observed" else "surge",
        "summary": {
            "city_total_cases": sum(
                float(r.get("observed_cases_w") or r.get("total_forecast_cases") or r.get("total_forecast") or 0.0)
                if mode == "observed"
                else float(r.get("forecast_w_cases") or 0.0)
                for r in ranked
            ),
            "very_high_count": sum(1 for r in ranked if _recommended_class(r, mode) == "very_high"),
            "priority_count": (
                sum(1 for r in ranked if float(r.get("observed_cases_w") or r.get("total_forecast_cases") or 0.0) > 0.0)
                if mode == "observed"
                else sum(1 for r in ranked if bool(r.get("priority_eligible")))
            ),
            "top_name": (top_row or {}).get("pretty_name") or (top_row or {}).get("name"),
            "top_value": _recommended_value(top_row, mode) if top_row else None,
        },
        "rows": ranked,
    }
    _action_priority_cache[cache_key] = resp
    return resp


@router.get("/rankings")
def get_forecast_rankings(
    period: str = Query("1m"),
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    ranking_basis: str = Query("incidence"),
    data_mode: str = Query("forecast"),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)
    weeks_to_sum = PERIOD_WEEKS.get(period, 4)
    basis = str(ranking_basis or "incidence").strip().lower()
    if basis not in RANKING_BASIS_SET:
        basis = "incidence"
    mode = str(data_mode or "forecast").strip().lower()
    if mode not in DATA_MODE_SET:
        mode = "forecast"
    if mode == "observed" and basis == "surge":
        basis = "cases"

    cache_key = (rid, model, period, basis, mode)
    if cache_key in _rankings_cache:
        return _rankings_cache[cache_key]

    pop_map = _load_population_map(sb)

    brg = (sb.table("barangays").select("name, display_name").execute().data) or []
    display_map = {
        normalize_name(b["name"]): (b.get("display_name") or b["name"])
        for b in brg
        if b.get("name")
    }

    # Selected-model forecast rows
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

    # Both-model forecast rows for summary table columns
    forecast_all_q = (
        sb.table("barangay_forecasts_long")
        .select("name, model_name, week_start, yhat")
        .eq("run_id", rid)
        .in_("model_name", ["prophet", "arima"])
        .eq("horizon_type", "future")
        .order("name")
        .order("model_name")
        .order("week_start")
    )
    forecast_all_rows = fetch_all(forecast_all_q)
    grouped_by_model: dict[str, dict[str, list[dict]]] = {"prophet": {}, "arima": {}}
    for row in forecast_all_rows:
        nm = normalize_name(row["name"])
        m = str(row.get("model_name") or "").strip().lower()
        if m not in grouped_by_model:
            continue
        grouped_by_model[m].setdefault(nm, []).append(row)

    # --- Get latest two observed weeks (city-level calendar)
    city_weeks = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(max(2, SURGE_HISTORY_WEEKS, SURGE_FALLBACK_BASELINE_WEEKS, weeks_to_sum))
        .execute()
        .data
    ) or []

    if not city_weeks:
        city_weeks = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(max(2, SURGE_HISTORY_WEEKS, SURGE_FALLBACK_BASELINE_WEEKS, weeks_to_sum))
            .execute()
            .data
        ) or []

    latest_week_date = city_weeks[0]["week_start"] if len(city_weeks) >= 1 else None
    prev_week_date = city_weeks[1]["week_start"] if len(city_weeks) >= 2 else None

    weeks_for_trend = [w for w in [latest_week_date, prev_week_date] if w is not None]
    weeks_for_surge_short = [x.get("week_start") for x in city_weeks[:SURGE_HISTORY_WEEKS] if x.get("week_start") is not None]
    weeks_for_surge_long = [x.get("week_start") for x in city_weeks[:SURGE_FALLBACK_BASELINE_WEEKS] if x.get("week_start") is not None]
    weeks_for_observed = [x.get("week_start") for x in city_weeks[:weeks_to_sum] if x.get("week_start") is not None]
    weeks_for_weekly = list(dict.fromkeys(weeks_for_trend + weeks_for_surge_long + weeks_for_observed))
    future_week_starts = sorted({str(r.get("week_start")) for r in forecasts if r.get("week_start") is not None})
    forecast_window = future_week_starts[:weeks_to_sum]
    observed_window = sorted([str(x) for x in weeks_for_observed])
    period_start_week = observed_window[0] if mode == "observed" and observed_window else (forecast_window[0] if forecast_window else None)
    period_end_week = observed_window[-1] if mode == "observed" and observed_window else (forecast_window[-1] if forecast_window else None)

    # --- Fetch only barangay rows for trend + surge windows
    weekly_rows_raw = []
    if weeks_for_weekly:
        weekly_rows_raw = fetch_all(
            sb.table("barangay_weekly_runs")
            .select("name, cases, week_start")
            .eq("run_id", rid)
            .in_("week_start", weeks_for_weekly)
        )

    if not weekly_rows_raw and weeks_for_weekly:
        weekly_rows_raw = fetch_all(
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .in_("week_start", weeks_for_weekly)
        )

    # --- Build grouped_weekly with newest first + week lookup for zero-fill windows
    grouped_weekly = {}
    weekly_lookup = {}
    for row in weekly_rows_raw:
        nm = normalize_name(row["name"])
        grouped_weekly.setdefault(nm, []).append(row)
        ws = row.get("week_start")
        if ws is not None:
            weekly_lookup.setdefault(nm, {})[str(ws)] = float(row.get("cases") or 0.0)

    for nm in grouped_weekly:
        grouped_weekly[nm].sort(key=lambda r: r["week_start"], reverse=True)

    rows_tmp, case_values, inc_values, surge_values = [], [], [], []

    all_names = set(grouped_future.keys()) | set(grouped_weekly.keys()) | set(display_map.keys())

    for name in sorted(all_names):
        future_rows = grouped_future.get(name, [])
        total_forecast = sum(float(r.get("yhat") or 0.0) for r in future_rows[:weeks_to_sum])

        weekly = grouped_weekly.get(name, [])
        weekly_recent2 = weekly[:2]
        series = weekly_lookup.get(name, {})
        last2_fore = [{"forecast": float(r.get("yhat") or 0.0)} for r in future_rows[-2:]] if len(future_rows) >= 2 else []
        trend, last_week, this_week, trend_source, trend_message = compute_hybrid_trend(weekly_recent2, last2_fore)

        pop = pop_map.get(name)
        inc = (float(total_forecast) / float(pop) * 100000.0) if pop and pop > 0 else None
        observed_w_cases = (
            sum(float(series.get(str(ws), 0.0)) for ws in weeks_for_observed)
            if weeks_for_observed
            else 0.0
        )
        observed_w_incidence = (float(observed_w_cases) / float(pop) * 100000.0) if pop and pop > 0 else None
        prophet_forecast_w = sum(float(r.get("yhat") or 0.0) for r in grouped_by_model["prophet"].get(name, [])[:weeks_to_sum])
        arima_forecast_w = sum(float(r.get("yhat") or 0.0) for r in grouped_by_model["arima"].get(name, [])[:weeks_to_sum])
        forecast_w_cases = sum(float(r.get("yhat") or 0.0) for r in future_rows[:weeks_to_sum])
        # Adaptive baseline:
        # use 8W only when recent signal is sufficiently stable, else fallback to 26W.
        short_vals = [float(series.get(str(ws), 0.0)) for ws in weeks_for_surge_short] if weeks_for_surge_short else []
        long_vals = [float(series.get(str(ws), 0.0)) for ws in weeks_for_surge_long] if weeks_for_surge_long else []
        nonzero_8w = int(sum(1 for v in short_vals if v > 0.0))
        if nonzero_8w >= int(SURGE_MIN_NONZERO_FOR_SHORT_BASELINE):
            baseline_window_vals = short_vals
            baseline_weeks_used = int(SURGE_HISTORY_WEEKS)
        else:
            baseline_window_vals = long_vals
            baseline_weeks_used = int(SURGE_FALLBACK_BASELINE_WEEKS)
        denom = float(len(baseline_window_vals)) if len(baseline_window_vals) else 1.0
        past_8w_avg_cases = float(sum(baseline_window_vals)) / denom
        baseline_expected_w = float(past_8w_avg_cases) * float(weeks_to_sum)
        surge_score = float(forecast_w_cases) / (float(baseline_expected_w) + SURGE_EPSILON)
        surge_eligible = float(forecast_w_cases) >= float(SURGE_MIN_FORECAST_CASES)
        baseline_eligible = float(baseline_expected_w) >= 1.0
        priority_eligible = bool(surge_eligible and baseline_eligible)
        display_cases = observed_w_cases if mode == "observed" else total_forecast
        display_incidence = observed_w_incidence if mode == "observed" else inc

        rows_tmp.append(
            (
                name,
                total_forecast,
                inc,
                observed_w_cases,
                observed_w_incidence,
                prophet_forecast_w,
                arima_forecast_w,
                display_cases,
                display_incidence,
                trend,
                last_week,
                this_week,
                trend_source,
                trend_message,
                forecast_w_cases,
                past_8w_avg_cases,
                baseline_expected_w,
                surge_score,
                surge_eligible,
                baseline_eligible,
                priority_eligible,
                baseline_weeks_used,
                nonzero_8w,
            )
        )
        case_values.append(float(display_cases))
        if display_incidence is not None:
            inc_values.append(float(display_incidence))
        surge_values.append(float(surge_score))

    case_breaks = jenks_breaks_safe(case_values, n_classes=5)
    inc_breaks = jenks_breaks_safe(inc_values, n_classes=5)
    surge_breaks = jenks_breaks_safe(surge_values, n_classes=5)

    results = []
    for (
        name,
        total_forecast,
        inc,
        observed_w_cases,
        observed_w_incidence,
        prophet_forecast_w,
        arima_forecast_w,
        display_cases,
        display_incidence,
        trend,
        last_week,
        this_week,
        trend_source,
        trend_message,
        forecast_w_cases,
        past_8w_avg_cases,
        baseline_expected_w,
        surge_score,
        surge_eligible,
        baseline_eligible,
        priority_eligible,
        baseline_weeks_used,
        nonzero_8w,
    ) in rows_tmp:
        cases_class = jenks_class(float(display_cases), case_breaks) if display_cases is not None else "unknown"
        burden_class = jenks_class(float(display_incidence), inc_breaks) if display_incidence is not None else "unknown"
        surge_class = jenks_class(float(surge_score), surge_breaks) if surge_score is not None else "unknown"

        results.append(
            {
                "name": name,
                "pretty_name": display_map.get(name, name),
                "total_forecast": round(display_cases, 2),
                "total_forecast_cases": round(display_cases, 2),
                "total_forecast_incidence_per_100k": display_incidence,
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
                "forecast_w_cases": round(float(forecast_w_cases), 4),
                "past_8w_avg_cases": round(float(past_8w_avg_cases), 4),
                "baseline_expected_w": round(float(baseline_expected_w), 4),
                "surge_score": round(float(surge_score), 6),
                "surge_class": surge_class,
                "surge_eligible": bool(surge_eligible),
                "baseline_eligible": bool(baseline_eligible),
                "priority_eligible": bool(priority_eligible),
                "baseline_weeks_used": int(baseline_weeks_used),
                "nonzero_weeks_8w": int(nonzero_8w),
                "observed_cases_w": round(float(observed_w_cases), 4),
                "observed_incidence_w": observed_w_incidence,
                "prophet_forecast_w": round(float(prophet_forecast_w), 4),
                "arima_forecast_w": round(float(arima_forecast_w), 4),
            }
        )

    if basis == "surge":
        results.sort(
            key=lambda x: (
                1 if bool(x.get("surge_eligible")) else 0,
                float(x.get("surge_score") or 0.0),
                float(x.get("total_forecast_cases") or 0.0),
            ),
            reverse=True,
        )
    elif basis == "cases":
        if mode == "observed":
            results.sort(
                key=lambda x: (
                    float(x.get("observed_cases_w") or x.get("total_forecast_cases") or 0.0),
                    float(x.get("observed_incidence_w") or x.get("total_forecast_incidence_per_100k") or 0.0)
                    if float(x.get("observed_cases_w") or x.get("total_forecast_cases") or 0.0) >= OBSERVED_INCIDENCE_TIEBREAK_MIN_CASES
                    else float("-inf"),
                    str(x.get("name") or ""),
                ),
                reverse=True,
            )
        else:
            results.sort(key=lambda x: float(x.get("total_forecast_cases") or 0.0), reverse=True)
    else:
        results.sort(key=lambda x: float(x.get("total_forecast_incidence_per_100k") or 0.0), reverse=True)

    resp = {
        "period": period,
        "weeks_to_sum": weeks_to_sum,
        "data_mode": mode,
        "ranking_basis": basis,
        "baseline_weeks": SURGE_HISTORY_WEEKS,
        "baseline_fallback_weeks": SURGE_FALLBACK_BASELINE_WEEKS,
        "baseline_min_nonzero_8w": SURGE_MIN_NONZERO_FOR_SHORT_BASELINE,
        "surge_epsilon": SURGE_EPSILON,
        "surge_min_forecast_cases": SURGE_MIN_FORECAST_CASES,
        "observed_incidence_tiebreak_min_cases": OBSERVED_INCIDENCE_TIEBREAK_MIN_CASES,
        "ranking_formula_version": RANKING_FORMULA_VERSION,
        "data_last_updated": latest_week_date,
        "model_current_date": latest_week_date,
        "user_current_date": str(date.today()),
        "period_start_week": period_start_week,
        "period_end_week": period_end_week,
        "rankings": results,
        "run_id": rid,
        "model_name": model,
        "horizon_type": "future",
        "jenks_breaks_incidence": inc_breaks,
        "jenks_breaks_cases": case_breaks,
        "jenks_breaks_surge": surge_breaks,
    }

    _rankings_cache[cache_key] = resp
    return resp
