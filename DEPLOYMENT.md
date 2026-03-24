# Deployment Guide

## Architecture

This project has three deployable parts:

1. `dengue-web` on Vercel
2. `api.main:app` on Railway as the public API
3. `api.worker` on Railway as the background upload processor

Supabase remains the shared backend for auth, storage, and database tables.

## Vercel

Deploy the `dengue-web` folder.

### Environment variables

```env
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Railway API Service

Deploy the repo root.

### Start command

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

### Environment variables

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
UPLOAD_BUCKET=dengue-uploads
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://your-frontend-domain.vercel.app
```

Optional for Vercel preview deployments:

```env
CORS_ORIGIN_REGEX=https://.*\.vercel\.app
```

## Railway Worker Service

Create a second Railway service from the same repo.

### Start command

```bash
python -m api.worker
```

### Environment variables

Use the same Supabase variables as the API service, plus:

```env
DENGUARD_MASTER_DATA_CSV=/data/intermediate/dengue_master_cleaned.csv
DENGUARD_OUT_ROOT=/data/intermediate/runs
DENGUARD_POLICY_LOCAL_PERF_CSV=/app/policies/local_model_performance_backtest_2022-12-26_3b3037b5.csv
WORKER_POLL_SECONDS=15
```

Recommended:

- mount a persistent volume at `/data`
- point `DENGUARD_MASTER_DATA_CSV` and `DENGUARD_OUT_ROOT` into that volume

Without persistent storage, upload processing will still work temporarily, but the cleaned master dataset can be lost after container replacement or redeploy.

## Upload Processing Flow

1. Admin uploads file through the dashboard
2. API writes upload metadata and a queued run into Supabase
3. Worker claims the queued upload
4. Worker downloads the file from Supabase storage
5. Worker runs `run_production`
6. Pipeline exports results to Supabase and publishes the active run
7. Dashboard refreshes to the new run
