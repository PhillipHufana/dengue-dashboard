# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .geo import router as geo_router
from .forecast import router as forecast_router
from .timeseries import router as timeseries_router

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

# Routers
app.include_router(geo_router)
app.include_router(forecast_router, prefix="/forecast")
app.include_router(timeseries_router, prefix="/timeseries")

@app.get("/health")
def health():
    return {"status": "ok"}
