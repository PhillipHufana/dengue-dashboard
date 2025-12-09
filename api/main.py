# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .geo import router as geo_router
from .forecast import router as forecast_router
from .timeseries import router as timeseries_router
from .forecast_rankings import router as rankings_router
from datetime import datetime

app = FastAPI(
    title="Denguard API",
    description="Provides dengue forecasts, barangay boundaries, geospatial overlays.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/data/info")
def data_info():
    sb = get_supabase()

    # find last historical date
    resp = (
        sb.table("barangay_weekly")
        .select("week_start")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if not resp:
        last_hist = None
    else:
        last_hist = resp[0]["week_start"]

    return {
        "last_historical_date": last_hist,
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "data_age_days": (
            (datetime.now() - datetime.fromisoformat(last_hist)).days if last_hist else None
        )
    }

# Routers
app.include_router(geo_router)
app.include_router(forecast_router, prefix="/forecast")
app.include_router(timeseries_router, prefix="/timeseries")
app.include_router(rankings_router, prefix="/forecast")

@app.get("/health")
def health():
    return {"status": "ok"}
