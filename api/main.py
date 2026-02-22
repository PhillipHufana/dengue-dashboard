# api/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .supabase_client import get_supabase
from .geo import router as geo_router
from .forecast import router as forecast_router
from .timeseries import router as timeseries_router
from .forecast_rankings import router as rankings_router
from datetime import datetime
from .info import router as info_router
from .admin_uploads import router as admin_uploads_router
from .public_meta import router as public_meta_router
# from .diagnostics import router as diag_router
# api/main.py
import traceback
from fastapi.responses import JSONResponse
app = FastAPI(
    title="Denguard API",
    description="Provides dengue forecasts, barangay boundaries, geospatial overlays.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/debug/ping-supabase")
def ping_supabase():
    sb = get_supabase()
    # very small query
    rows = sb.table("runs").select("run_id").limit(1).execute().data or []
    return {"ok": True, "n": len(rows)}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )
# Routers
app.include_router(geo_router)
app.include_router(forecast_router, prefix="/forecast")
app.include_router(timeseries_router, prefix="/timeseries")
app.include_router(rankings_router, prefix="/forecast")
app.include_router(info_router)
# app.include_router(diag_router)

# NEW
app.include_router(admin_uploads_router)
app.include_router(public_meta_router)

@app.get("/health")
def health():
    return {"status": "ok"}
