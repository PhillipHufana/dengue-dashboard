# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .geo import router as geo_router
from .forecast import router as forecast_router

app = FastAPI(
    title="Denguard API",
    description="Provides barangay boundaries, dengue forecasts, and city-level data.",
    version="1.0.0",
)

# CORS (allow requests from your Next.js frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # You can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(geo_router, prefix="/geo", tags=["Geospatial"])
app.include_router(forecast_router, prefix="/forecast", tags=["Forecasts"])


@app.get("/health")
def health():
    return {"status": "ok"}
