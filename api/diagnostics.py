from fastapi import APIRouter, Query
from typing import Optional
from .supabase_client import get_supabase
from .run_helpers import resolve_run_id, resolve_model_name
from .utils import normalize_name

router = APIRouter(prefix="/diag", tags=["diag"])

@router.get("/pipeline")
def pipeline_diag(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # 1) weekly table
    bw_latest = (
        sb.table("barangay_weekly")
        .select("week_start")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    latest_weekly = bw_latest[0]["week_start"] if bw_latest else None

    bw_count_latest_week = 0
    if latest_weekly:
        bw_count_latest_week = len(
            (sb.table("barangay_weekly")
             .select("name")
             .eq("week_start", latest_weekly)
             .execute()
             .data) or []
        )

    # 2) future forecasts count for this run/model
    fc = (
        sb.table("barangay_forecasts_long")
        .select("name, week_start", count="exact")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
    )
    future_forecast_rows = fc.count or 0

    # 3) unique barangays in forecasts
    # (cheap-ish if you have 182*52; you can later replace with a view)
    names = (
        sb.table("barangay_forecasts_long")
        .select("name")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
        .data
    ) or []
    unique_forecast_barangays = len({r["name"] for r in names if r.get("name")})

    # 4) latest view rows
    latest_fc = (
        sb.table("barangay_forecasts_long")
        .select("name")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .order("name")
        .order("week_start")
        .execute()
        .data
    ) or []
    latest_view_rows = len({normalize_name(r["name"]) for r in latest_fc if r.get("name")})

    return {
        "resolved": {"run_id": rid, "model_name": model},
        "weekly": {
            "latest_week_start": latest_weekly,
            "rows_at_latest_week": bw_count_latest_week,
            "expected_barangays": 182,
        },
        "forecasts_future": {
            "rows": future_forecast_rows,
            "unique_barangays": unique_forecast_barangays,
            "expected_unique_barangays": 182,
        },
        "latest_barangay_forecast_view": {
            "rows": latest_view_rows,
            "expected_rows": 182,
        },
    }
