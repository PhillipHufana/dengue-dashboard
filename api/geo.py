# api/geo.py
from fastapi import APIRouter, HTTPException
import json
from pathlib import Path

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@router.get("/boundaries")
def get_boundaries():
    """Return Davao polygon boundaries for Leaflet."""
    geo_path = DATA_DIR / "DAVAO_Poly_geo.geojson"
    if not geo_path.exists():
        raise HTTPException(status_code=404, detail="Polygon GeoJSON not found")

    with geo_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/points")
def get_points():
    """Barangay point markers."""
    geo_path = DATA_DIR / "DAVAO_Points_geo.geojson"
    if not geo_path.exists():
        raise HTTPException(status_code=404, detail="Points GeoJSON not found")

    with geo_path.open("r", encoding="utf-8") as f:
        return json.load(f)
