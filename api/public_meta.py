from __future__ import annotations
from fastapi import APIRouter
from .supabase_client import get_supabase

router = APIRouter(tags=["meta"])

@router.get("/active-run")
def get_active_run():
    sb = get_supabase()
    row = (
        sb.table("active_runs")
        .select("active_run_id, updated_at")
        .eq("id", 1)
        .limit(1)
        .execute()
        .data
    ) or []
    if row and row[0].get("active_run_id"):
        return {"run_id": row[0]["active_run_id"], "source": "active_runs", "updated_at": row[0].get("updated_at")}

    latest = (
        sb.table("runs")
        .select("run_id, created_at")
        .eq("status", "succeeded")
        .order("created_at", desc=True)
        .order("run_id", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    if latest:
        return {"run_id": latest[0]["run_id"], "source": "latest_succeeded", "updated_at": latest[0].get("created_at")}

    return {"run_id": None, "source": "none", "updated_at": None}

