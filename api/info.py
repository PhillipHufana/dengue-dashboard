# api/info.py
from fastapi import APIRouter
from datetime import datetime
from typing import Optional
from .supabase_client import get_supabase
from .run_helpers import resolve_run_id

router = APIRouter(tags=["meta"])

@router.get("/data/info")
def get_data_info(run_id: Optional[str] = None):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)

    latest = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []

    if not latest:
        latest = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []

    last_update = latest[0]["week_start"] if latest else None

    return {
        "last_historical_date": last_update,
        "server_date": datetime.now().strftime("%Y-%m-%d"),
        "run_id": rid,
    }