# api/geo.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from .supabase_client import get_supabase
from typing import Optional, Dict, Any, List
import json
from .run_helpers import resolve_run_id, resolve_model_name
from .risk import risk_from_baseline_percentiles
from .forecast import _load_weekly_history, _load_population_map

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/choropleth")
def get_choropleth(
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # 1) polygons
    brg_rows = (
        sb.table("barangays")
        .select("name, display_name, geom_json")
        .execute()
        .data
    ) or []

    # 2) latest forecasts (view)
    latest_rows = (
        sb.table("latest_barangay_forecast")
        .select("name, week_start, yhat")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
        .data
    ) or []

    forecast_map = {r["name"]: r for r in latest_rows}

    history = _load_weekly_history(sb, rid)
    pop_map = _load_population_map(sb)


    features = []
    for b in brg_rows:
        nm = b["name"]
        geom = b.get("geom_json")
        if not geom:
            continue

        fr = forecast_map.get(nm)
        fc = float(fr["yhat"]) if fr and fr.get("yhat") is not None else None
        wk = fr["week_start"] if fr else None

        series = history.get(nm, [])
        pop = pop_map.get(nm)

        if fc is None:
            risk_pack = {
                "forecast_incidence_per_100k": None,
                "risk_level_cases": "unknown",
                "risk_level_incidence": None,
            }
        else:
            risk_pack = risk_from_baseline_percentiles(
                forecast_cases=float(fc),
                history_cases=series,
                population=pop,
            )


        properties = {
            "name": nm,
            "display_name": b.get("display_name") or nm,
            "latest_future_week": wk,

            # 🔥 REQUIRED FOR FRONTEND
            "risk_level": risk_pack["risk_level_cases"],
            "latest_forecast": fc,

            "forecast_cases": fc,
            "forecast_incidence_per_100k": risk_pack["forecast_incidence_per_100k"],
            "risk_level_cases": risk_pack["risk_level_cases"],
            "risk_level_incidence": risk_pack["risk_level_incidence"],

            "run_id": rid,
            "model_name": model,
            "horizon_type": "future",

            # keep if frontend expects:
            "latest_cases": 0,
            "latest_week": None,
        }

        features.append({"type": "Feature", "geometry": geom, "properties": properties})


    return {
    "type": "FeatureCollection",
    "run_id": rid,
    "model_name": model,
    "horizon_type": "future",
    "features": features
    }


@router.get("/hotspots/top")
def dengue_hotspots_top(
    n: int = 10,
    run_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    sb = get_supabase()
    rid = resolve_run_id(sb, run_id)
    model = resolve_model_name(sb, rid, model_name)

    # latest observed week_start (shared baseline)
    city = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", rid)
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []

    if not city:
        city = (
            sb.table("city_weekly")
            .select("week_start")
            .order("week_start", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
    latest_ws = city[0]["week_start"] if city else None

    weekly = (
        sb.table("barangay_weekly_runs")
        .select("name, cases, week_start")
        .eq("run_id", rid)
        .eq("week_start", latest_ws)
        .execute()
        .data
    ) or []

    if not weekly:
        weekly = (
            sb.table("barangay_weekly")
            .select("name, cases, week_start")
            .eq("week_start", latest_ws)
            .execute()
            .data
        ) or []
    latest_cases = {r["name"]: int(r.get("cases") or 0) for r in weekly}

    frows = (
        sb.table("latest_barangay_forecast")
        .select("name, week_start, yhat")
        .eq("run_id", rid)
        .eq("model_name", model)
        .eq("horizon_type", "future")
        .execute()
        .data
    ) or []
    latest_fc = {r["name"]: float(r.get("yhat") or 0.0) for r in frows}

    all_brgy = set(latest_cases) | set(latest_fc)
    hotspots = []
    for nm in all_brgy:
        cases = latest_cases.get(nm, 0)
        forecast = latest_fc.get(nm, 0.0)
        growth = float(forecast) - float(cases)

        hotspots.append(
            {"name": nm, "latest_cases": cases, "latest_forecast": forecast, "growth": growth}
        )

    hotspots.sort(key=lambda x: x["growth"], reverse=True)
    return hotspots[:n]
