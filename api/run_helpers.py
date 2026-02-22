# ============================================================
# file: api/run_helpers.py
# PATCH: resolve run_id from active_runs first, then fallback
# ============================================================
from __future__ import annotations
from typing import Optional

DEFAULT_MODEL = "preferred"


def resolve_run_id(sb, run_id: Optional[str]) -> str:
    if run_id:
        return run_id

    # 1) Prefer published pointer
    active = (
        sb.table("active_runs")
        .select("active_run_id")
        .eq("id", 1)
        .limit(1)
        .execute()
        .data
    )
    if active and active[0].get("active_run_id"):
        return active[0]["active_run_id"]

    # 2) Fallback: latest succeeded run
    latest = (
        sb.table("runs")
        .select("run_id")
        .eq("status", "succeeded")
        .order("created_at", desc=True)
        .order("run_id", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not latest:
        raise RuntimeError("No succeeded runs found in database")
    return latest[0]["run_id"]


def resolve_model_name(sb, run_id: str, model_name: Optional[str]) -> str:
    if model_name:
        return model_name

    rows = (
        sb.table("city_forecasts_long")
        .select("model_name")
        .eq("run_id", run_id)
        .execute()
        .data
    ) or []
    models = sorted({r["model_name"] for r in rows if r.get("model_name")})

    if not models:
        raise RuntimeError(f"No models found for run_id={run_id}")

    return DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]