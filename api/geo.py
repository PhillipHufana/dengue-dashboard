# api/geo.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any
from .supabase_client import get_supabase
import unicodedata

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
    """
    FULL normalization to match dengue pipeline's Barangay_standardized.
    Removes accents, (Pob.), (Lasang), hyphens, double spaces, etc.
    """
    if not x:
        return ""

    # Lowercase + strip
    x = x.strip().lower()

    # Remove bracketed suffix "(Pob.)", "(Lasang)", "(Licanan)", etc.
    if "(" in x:
        x = x.split("(")[0].strip()

    # Remove accents (Pequeño → pequeno)
    x = ''.join(
        c for c in unicodedata.normalize('NFD', x)
        if unicodedata.category(c) != 'Mn'
    )

    # Replace hyphens with spaces
    x = x.replace("-", " ")

    # Collapse multiple spaces
    x = " ".join(x.split())

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

    return {"type": "FeatureCollection", "features": features}
