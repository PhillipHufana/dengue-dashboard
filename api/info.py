# api/info.py
from fastapi import APIRouter
from datetime import datetime

from .supabase_client import get_supabase

router = APIRouter(tags=["meta"])

@router.get("/data/info")
def get_data_info():
    sb = get_supabase()

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
