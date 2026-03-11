# ============================================================
# file: api/run_helpers.py
# PATCH: resolve run_id from active_runs first, then fallback
# ============================================================
from __future__ import annotations
import json
import re
from typing import Optional, List

DEFAULT_MODEL = "preferred"
UI_MODEL_SET = {"preferred", "prophet", "arima"}


def _fetch_all_model_names(sb, table: str, run_id: str) -> set[str]:
    out: set[str] = set()
    start = 0
    page_size = 1000
    while True:
        rows = (
            sb.table(table)
            .select("model_name")
            .eq("run_id", run_id)
            .eq("horizon_type", "future")
            .range(start, start + page_size - 1)
            .execute()
            .data
        ) or []
        for r in rows:
            m = str(r.get("model_name") or "").strip()
            if m:
                out.add(m)
        if len(rows) < page_size:
            break
        start += page_size
    return out


def _run_has_dashboard_payload(sb, run_id: str) -> bool:
    city_count = (
        sb.table("city_forecasts_long")
        .select("run_id", count="exact")
        .eq("run_id", run_id)
        .eq("horizon_type", "future")
        .execute()
    )
    brgy_count = (
        sb.table("barangay_forecasts_long")
        .select("run_id", count="exact")
        .eq("run_id", run_id)
        .eq("horizon_type", "future")
        .execute()
    )
    c = int(getattr(city_count, "count", 0) or 0)
    b = int(getattr(brgy_count, "count", 0) or 0)
    if not (c > 0 and b > 0):
        return False

    # Ensure this run is valid for dashboard model toggle:
    # at least one UI model exists in both city and barangay future forecasts.
    city_models = {m for m in _fetch_all_model_names(sb, "city_forecasts_long", run_id) if m in UI_MODEL_SET}
    brgy_models = {m for m in _fetch_all_model_names(sb, "barangay_forecasts_long", run_id) if m in UI_MODEL_SET}
    return len(city_models & brgy_models) > 0


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
        active_run_id = active[0]["active_run_id"]
        if _run_has_dashboard_payload(sb, active_run_id):
            return active_run_id

    # 2) Fallback: latest succeeded run with dashboard payload
    latest = (
        sb.table("runs")
        .select("run_id")
        .eq("status", "succeeded")
        .order("created_at", desc=True)
        .order("run_id", desc=True)
        .limit(20)
        .execute()
        .data
    )
    if not latest:
        raise RuntimeError("No succeeded runs found in database")
    for row in latest:
        rid = row.get("run_id")
        if rid and _run_has_dashboard_payload(sb, rid):
            return rid
    # Last resort: keep old behavior
    return latest[0]["run_id"]


def available_models_for_run(sb, run_id: str) -> List[str]:
    city_models = _fetch_all_model_names(sb, "city_forecasts_long", run_id)
    brgy_models = _fetch_all_model_names(sb, "barangay_forecasts_long", run_id)

    city_models = {m for m in city_models if m in UI_MODEL_SET}
    brgy_models = {m for m in brgy_models if m in UI_MODEL_SET}

    # Dashboard is barangay-first; prefer models that exist in barangay future artifacts.
    if brgy_models:
        return sorted(brgy_models)
    return sorted(city_models)


def resolve_model_name(sb, run_id: str, model_name: Optional[str]) -> str:
    models = available_models_for_run(sb, run_id)

    if not models:
        raise RuntimeError(f"No models found for run_id={run_id}")

    if model_name and model_name in models:
        return model_name

    # If requested model is missing, gracefully fall back to available default.
    return DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]


def resolve_disagg_scheme_for_run(sb, run_id: str) -> Optional[str]:
    rows = (
        sb.table("runs")
        .select("data_version")
        .eq("run_id", run_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not rows:
        return None
    dv = rows[0].get("data_version")
    if dv is None:
        return None
    if isinstance(dv, dict):
        v = dv.get("disagg_scheme")
        return str(v).lower().strip() if v else None
    s = str(dv).strip()
    if not s:
        return None
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            v = obj.get("disagg_scheme")
            return str(v).lower().strip() if v else None
        except Exception:
            pass
    m = re.search(r"disagg_scheme\s*[:=]\s*([a-zA-Z_]+)", s)
    if m:
        return m.group(1).lower().strip()
    return None
