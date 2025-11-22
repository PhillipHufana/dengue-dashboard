# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .geo import router as geo_router
from .forecast import router as forecast_router
from api import geo


app = FastAPI(
    title="Denguard API",
    description="Provides dengue forecasts, barangay boundaries, geospatial overlays.",
    version="1.0.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your Next.js domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route groups
app.include_router(geo.router)  # NO prefix here
app.include_router(forecast_router, prefix="/forecast")


@app.get("/health")
def health():
    return {"status": "ok"}
