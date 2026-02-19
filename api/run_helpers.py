# api/run_helpers.py
from __future__ import annotations
from typing import Optional, List

DEFAULT_MODEL = "preferred"

def resolve_run_id(sb, run_id: Optional[str]) -> str:
    if run_id:
        return run_id

    latest = (
        sb.table("runs")
        .select("run_id")
        .order("created_at", desc=True)
        .order("run_id", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not latest:
        raise RuntimeError("No runs found in database")
    return latest[0]["run_id"]

def resolve_model_name(sb, run_id: str, model_name: Optional[str]) -> str:
    if model_name:
        return model_name

    # default to preferred if present, else first available
    rows = (
        sb.table("barangay_forecasts_long")
        .select("model_name")
        .eq("run_id", run_id)
        .execute()
        .data
    ) or []
    models = sorted({r["model_name"] for r in rows if r.get("model_name")})

    if not models:
        raise RuntimeError(f"No models found for run_id={run_id}")

    return DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]
