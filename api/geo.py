# api/geo.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any, List

from .supabase_client import get_supabase

router = APIRouter(prefix="/geo")


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLY_PATH = DATA_DIR / "DAVAO_Poly_geo.geojson"


def _load_polygons() -> Dict[str, Any]:
    """Load polygon GeoJSON file."""
    if not POLY_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Polygon GeoJSON not found at {POLY_PATH}")

    with POLY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_name(x: str | None) -> str:
    if x is None:
        return ""
    return str(x).strip().lower()


@router.get("/choropleth")
def dengue_choropleth():
    """
    Returns full GeoJSON WITH dengue data merged into properties:

    properties = {
        name,
        latest_cases,
        latest_week,
        latest_forecast,
        latest_future_week,
        risk_level
    }
    """
    sb = get_supabase()

    # 1. Load raw polygon shapes
    geo = _load_polygons()
    features = geo.get("features", [])

    # 2. Load latest historical weekly cases from Supabase
    weekly_resp = (
        sb.table("barangay_weekly")
        .select("name, week_start, cases")
        .order("week_start", desc=True)
        .execute()
    )
    rows_weekly = weekly_resp.data or []

    latest_cases: Dict[str, Dict[str, Any]] = {}
    for row in rows_weekly:
        nm = _normalize_name(row["name"])
        if nm not in latest_cases:
            latest_cases[nm] = {
                "cases": row["cases"],
                "week_start": row["week_start"],
            }

    # 3. Load latest forecasts
    fcast_resp = (
        sb.table("barangay_forecasts")
        .select("name, week_start, final_forecast, is_future")
        .order("week_start", desc=True)
        .execute()
    )
    rows_fcast = fcast_resp.data or []

    latest_forecast: Dict[str, Dict[str, Any]] = {}
    for row in rows_fcast:
        nm = _normalize_name(row["name"])
        if nm not in latest_forecast:
            latest_forecast[nm] = {
                "forecast": row["final_forecast"],
                "week_start": row["week_start"],
                "is_future": row["is_future"],
            }

    # 4. Merge dengue data into polygon properties
    for feat in features:
        props = feat.setdefault("properties", {})

        # Polygon naming must match Supabase standardized lowercased names
        raw_name = (
            props.get("name")
            or props.get("NAME")
            or props.get("Barangay")
            or props.get("BRGY_NAME")
        )
        nm = _normalize_name(raw_name)

        # Overwrite polygon property for consistency
        props["name"] = nm

        # Latest actual cases
        if nm in latest_cases:
            props["latest_cases"] = latest_cases[nm]["cases"]
            props["latest_week"] = latest_cases[nm]["week_start"]
        else:
            props["latest_cases"] = 0
            props["latest_week"] = None

        # Latest forecast
        if nm in latest_forecast:
            props["latest_forecast"] = latest_forecast[nm]["forecast"]
            props["latest_future_week"] = latest_forecast[nm]["week_start"]
        else:
            props["latest_forecast"] = 0.0
            props["latest_future_week"] = None

        # Basic risk classification
        f = props["latest_forecast"] or 0
        if f < 5:
            risk = "low"
        elif f < 15:
            risk = "medium"
        else:
            risk = "high"

        props["risk_level"] = risk

    return {
        "type": "FeatureCollection",
        "features": features,
    }
