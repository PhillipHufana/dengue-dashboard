# api/choropleth.py
from fastapi import APIRouter, HTTPException
from .supabase_client import get_supabase
from .utils import normalize_name
import json

router = APIRouter(tags=["Choropleth"])


@router.get("/choropleth")
def get_choropleth_map():
    sb = get_supabase()

    # -----------------------------
    # 1. Load base GeoJSON
    # -----------------------------
    geo_resp = (
        sb.table("barangay_shapes")
        .select("geojson")
        .limit(1)
        .execute()
    )

    if not geo_resp.data:
        raise HTTPException(status_code=404, detail="GeoJSON not found")

    geojson = geo_resp.data[0]["geojson"]
    if isinstance(geojson, str):
        geojson = json.loads(geojson)

    # -----------------------------
    # 2. Load latest risk + forecast
    # -----------------------------
    rows = (
        sb.table("barangay_forecasts")
        .select("name, final_forecast, risk_level, week_start")
        .order("week_start", desc=True)
        .execute()
    ).data or []

    latest = {}
    seen = set()

    for row in rows:
        nm = normalize_name(row["name"])
        if nm not in seen:
            seen.add(nm)
            latest[nm] = {
                "forecast": row["final_forecast"],
                "risk_level": row.get("risk_level", "unknown"),
                "week_start": row["week_start"],
            }

    # -----------------------------
    # 3. Merge into GeoJSON features
    # -----------------------------
    for feature in geojson["features"]:
        raw_name = feature["properties"].get("ADM4_EN", "")
        nm = normalize_name(raw_name)

        data = latest.get(nm)

        feature["properties"]["risk_level"] = data["risk_level"] if data else "unknown"
        feature["properties"]["latest_forecast"] = (
            data["forecast"] if data else None
        )
        feature["properties"]["week_start"] = (
            data["week_start"] if data else None
        )

    return geojson
