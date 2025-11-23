# api/geo.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any
from .supabase_client import get_supabase
import unicodedata, re

router = APIRouter(prefix="/geo", tags=["geo"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLY_PATH = DATA_DIR / "DAVAO_Poly_geo.geojson"


def load_polygons() -> Dict[str, Any]:
    """Load polygon GeoJSON file."""
    if not POLY_PATH.exists():
        raise HTTPException(500, f"Polygon GeoJSON not found at {POLY_PATH}")

    with POLY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_name(x: str | None) -> str:
    if not x:
        return ""

    # lowercase
    x = x.lower().strip()

    # remove accents (e.g., pequeño → pequeno)
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()

    # remove (pob.) and similar suffixes
    x = re.sub(r"\(.*?\)", "", x)

    # convert hyphens to spaces
    x = x.replace("-", " ")

    # remove punctuation
    x = re.sub(r"[^a-z0-9 ]", "", x)

    # collapse multiple spaces
    x = re.sub(r"\s+", " ", x).strip()

    return x

@router.get("/choropleth")
def dengue_choropleth():
    """
    Returns full GeoJSON WITH dengue data merged into polygon properties.
    """
    sb = get_supabase()

    # Load polygons
    geo = load_polygons()
    features = geo.get("features", [])

    # Load latest weekly cases
    weekly = (
        sb.table("barangay_weekly")
        .select("name, week_start, cases")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    latest_cases = {}
    for row in weekly:
        nm = row["name"]
        if nm not in latest_cases:
            latest_cases[nm] = {
                "cases": row["cases"],
                "week": row["week_start"],
            }

    # Load forecasts
    fcast = (
        sb.table("barangay_forecasts")
        .select("name, week_start, final_forecast, is_future")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    latest_forecast = {}
    for row in fcast:
        nm = row["name"]
        if nm not in latest_forecast:
            latest_forecast[nm] = {
                "forecast": row["final_forecast"],
                "week": row["week_start"],
                "is_future": row["is_future"],
            }

    # Merge dengue values into polygons
    for feat in features:
        props = feat.setdefault("properties", {})

        # ADM4_EN = official barangay boundary name
        raw_name = (
            props.get("ADM4_EN")
            or props.get("ADM4_REF")
            or props.get("ADM4_PCODE")
        )

        nm = normalize_name(raw_name)
        props["name"] = nm

        # Set actual cases
        if nm in latest_cases:
            props["latest_cases"] = latest_cases[nm]["cases"]
            props["latest_week"] = latest_cases[nm]["week"]
        else:
            props["latest_cases"] = 0
            props["latest_week"] = None

        # Set forecast
        if nm in latest_forecast:
            props["latest_forecast"] = latest_forecast[nm]["forecast"]
            props["latest_future_week"] = latest_forecast[nm]["week"]
        else:
            props["latest_forecast"] = 0.0
            props["latest_future_week"] = None

        # Risk classification
        f = props["latest_forecast"] or 0
        if f < 5:
            props["risk_level"] = "low"
        elif f < 15:
            props["risk_level"] = "medium"
        else:
            props["risk_level"] = "high"

    # Remove non-barangay polygons
    features = [
        feat for feat in features
        if normalize_name(
            feat.get("properties", {}).get("ADM4_EN")
        ) != "mount apo national park under jurisdiction of davao city"
    ]


    return {"type": "FeatureCollection", "features": features}

@router.get("/hotspots/top")
def dengue_hotspots_top(n: int = 10):
    """
    Returns top N hotspot barangays based on:
    - latest_cases
    - latest_forecast
    - growth = forecast - cases
    - risk_level
    """

    sb = get_supabase()

    # ---- 1. LOAD LATEST CASES ----
    weekly = (
        sb.table("barangay_weekly")
        .select("name, week_start, cases")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    latest_cases = {}
    for row in weekly:
        nm = row["name"]
        if nm not in latest_cases:
            latest_cases[nm] = {
                "cases": row["cases"],
                "week": row["week_start"],
            }

    # ---- 2. LOAD LATEST FORECAST ----
    fcast = (
        sb.table("barangay_forecasts")
        .select("name, week_start, final_forecast, is_future")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    latest_forecast = {}
    for row in fcast:
        nm = row["name"]
        if nm not in latest_forecast:
            latest_forecast[nm] = {
                "forecast": row["final_forecast"],
                "week": row["week_start"],
                "is_future": row["is_future"]
            }

    # ---- 3. BUILD HOTSPOT LIST ----
    hotspots = []

    # Combine all barangay names from both tables
    all_brgy = set(latest_cases.keys()) | set(latest_forecast.keys())

    for name in all_brgy:
        cases = latest_cases.get(name, {}).get("cases", 0)
        forecast = latest_forecast.get(name, {}).get("forecast", 0)
        growth = forecast - cases

        # risk classification (same as choropleth)
        if forecast < 5:
            risk = "low"
        elif forecast < 15:
            risk = "medium"
        else:
            risk = "high"

        hotspots.append({
            "name": name,
            "latest_cases": cases,
            "latest_forecast": forecast,
            "growth": growth,
            "risk_level": risk,
        })

    # ---- 4. SORT AND RETURN TOP N ----
    hotspots_sorted = sorted(hotspots, key=lambda x: x["growth"], reverse=True)

    return hotspots_sorted[:n]
