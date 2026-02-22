# api/info.py
from fastapi import APIRouter
from datetime import datetime

from .supabase_client import get_supabase

router = APIRouter(tags=["meta"])

@router.get("/data/info")
def get_data_info():
    sb = get_supabase()

    # prefer published run
    active = (sb.table("active_runs").select("active_run_id").eq("id", 1).limit(1).execute().data) or []
    rid = active[0]["active_run_id"] if active and active[0].get("active_run_id") else None

    latest = []
    if rid:
        latest = (
            sb.table("barangay_weekly_runs")
            .select("week_start")
            .eq("run_id", rid)
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []

    # fallback legacy
    if not latest:
        latest = (
            sb.table("barangay_weekly")
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
    }
