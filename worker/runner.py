# =========================================
# file: worker/runner.py
# HTTP-only worker (no psycopg2 / no SUPABASE_DB_URL)
# Compatible with Supabase free tier IPv6-only direct DB.
# =========================================
from __future__ import annotations

import os
import time
import traceback
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from supabase import create_client

from denguard.config import DEFAULT_CFG, Config
from denguard.pipeline import run_production  # your entrypoint

load_dotenv()

POLL_SECONDS = int(os.environ.get("WORKER_POLL_SECONDS", "5"))
EXPECTED_BARANGAYS = int(os.environ.get("EXPECTED_BARANGAYS", "182"))
TMP_DIR = Path(os.environ.get("WORKER_TMP_DIR", "./.worker_tmp")).resolve()
OUT_BASE = Path(os.environ.get("WORKER_OUT_BASE", "intermediate")).resolve()
UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "dengue-uploads")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sb_admin():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def log_run(sb, run_id: str, level: str, event: str, message: str = "", payload: Optional[Dict[str, Any]] = None):
    payload = payload or {}
    sb.table("run_logs").insert(
        {"run_id": run_id, "level": level, "event": event, "message": message, "payload": payload}
    ).execute()


def set_run(sb, run_id: str, status: str, error_message: Optional[str] = None):
    payload: Dict[str, Any] = {"status": status}

    if status == "running":
        payload["started_at"] = _utc_now_iso()
        payload["finished_at"] = None
        payload["error_message"] = None

    if status in ("succeeded", "failed"):
        payload["finished_at"] = _utc_now_iso()
        payload["error_message"] = error_message

    sb.table("runs").update(payload).eq("run_id", run_id).execute()


def set_upload(sb, upload_id: str, status: str, error_message: Optional[str] = None):
    sb.table("upload_runs").update({"status": status, "error_message": error_message}).eq("upload_id", upload_id).execute()

def get_upload_status(sb, upload_id: str) -> str | None:
    rows = (
        sb.table("upload_runs")
        .select("status")
        .eq("upload_id", upload_id)
        .limit(1)
        .execute()
        .data
    ) or []
    return rows[0]["status"] if rows else None

def publish_active_run(sb, run_id: str):
    sb.table("active_runs").upsert(
        {"id": 1, "active_run_id": run_id, "updated_at": _utc_now_iso()},
        on_conflict="id",
    ).execute()


def download_upload(sb, storage_path: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    res = sb.storage.from_(UPLOAD_BUCKET).download(storage_path)

    if isinstance(res, (bytes, bytearray)):
        out_path.write_bytes(res)
        return
    if hasattr(res, "data") and isinstance(res.data, (bytes, bytearray)):
        out_path.write_bytes(res.data)
        return

    raise RuntimeError(f"Unexpected storage download response: {type(res)}")


def build_cfg_for_upload(run_id: str, upload_path: Path) -> Config:
    run_out_dir = OUT_BASE / "runs" / run_id
    cfg = DEFAULT_CFG
    return replace(
        cfg,
        run_kind="production",
        run_id=run_id,
        out_dir=str(run_out_dir),
        incoming_mode="full_refresh",
        raw_xlsx=str(upload_path),  # may be .csv or .xlsx
    )


def assert_publishable(sb, run_id: str) -> None:
    # city weekly rows
    city = sb.table("city_weekly_runs").select("run_id", count="exact").eq("run_id", run_id).execute()
    city_n = int(getattr(city, "count", 0) or 0)
    if city_n <= 0:
        raise RuntimeError("publishability failed: city_weekly_runs has 0 rows")

    # barangay weekly rows
    brgy = sb.table("barangay_weekly_runs").select("run_id", count="exact").eq("run_id", run_id).execute()
    brgy_n = int(getattr(brgy, "count", 0) or 0)
    if brgy_n <= 0:
        raise RuntimeError("publishability failed: barangay_weekly_runs has 0 rows")

    # estimate weeks from city_weekly_runs
    weeks_rows = (
        sb.table("city_weekly_runs")
        .select("week_start")
        .eq("run_id", run_id)
        .execute()
        .data
    ) or []
    n_weeks = len({r["week_start"] for r in weeks_rows if r.get("week_start")})
    expected_min = EXPECTED_BARANGAYS * max(1, n_weeks)
    if brgy_n < expected_min:
        raise RuntimeError(f"publishability failed: barangay_weekly_runs rows={brgy_n} < expected_min={expected_min}")

    # preferred future forecasts
    fc = (
        sb.table("barangay_forecasts_long")
        .select("run_id", count="exact")
        .eq("run_id", run_id)
        .eq("model_name", "preferred")
        .eq("horizon_type", "future")
        .execute()
    )
    fc_n = int(getattr(fc, "count", 0) or 0)
    if fc_n <= 0:
        raise RuntimeError("publishability failed: preferred future forecasts missing")


def claim_one(sb) -> Optional[Dict[str, Any]]:
    # 1) fetch oldest queued
    queued = (
        sb.table("upload_runs")
        .select("upload_id, run_id, storage_path, original_filename, status, created_at")
        .eq("status", "queued")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    ) or []
    if not queued:
        return None

    job = queued[0]
    upload_id = job["upload_id"]

    # 2) compare-and-set claim (queued -> running)
    sb.table("upload_runs").update({"status": "running"}).eq("upload_id", upload_id).eq("status", "queued").execute()

    # 3) confirm claim
    check = (
        sb.table("upload_runs")
        .select("upload_id, status")
        .eq("upload_id", upload_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not check or check[0].get("status") != "running":
        return None

    return job


def main():
    sb = sb_admin()
    print("worker started; polling queued uploads...")

    while True:
        job: Optional[Dict[str, Any]] = None

        try:
            job = claim_one(sb)
            if not job:
                time.sleep(POLL_SECONDS)
                continue

            upload_id = job["upload_id"]
            run_id = job["run_id"]
            storage_path = job["storage_path"]

            log_run(sb, run_id, "info", "claimed", payload={"upload_id": upload_id, "storage_path": storage_path})
            set_run(sb, run_id, "running", None)
            set_upload(sb, upload_id, "running", None)

            upload_local = TMP_DIR / upload_id / Path(storage_path).name
            download_upload(sb, storage_path, upload_local)

            cfg = build_cfg_for_upload(run_id, upload_local)

            # ---- preflight: stop if canceled before heavy pipeline ----
            st = get_upload_status(sb, upload_id)
            if st == "canceled":
                set_run(sb, run_id, "failed", "canceled by admin")
                set_upload(sb, upload_id, "canceled", "canceled by admin")
                log_run(sb, run_id, "warning", "canceled", message="Canceled before pipeline start")
                print(f"⛔ canceled upload {upload_id} before pipeline start")
                time.sleep(0.1)
                continue

            run_production(cfg)  # must export to supabase internally

            assert_publishable(sb, run_id)
            publish_active_run(sb, run_id)

            set_run(sb, run_id, "succeeded", None)
            set_upload(sb, upload_id, "succeeded", None)
            log_run(sb, run_id, "info", "published", payload={"active_run_id": run_id})

            print(f"✅ published run {run_id} from upload {upload_id}")

        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print(traceback.format_exc())

            if job and job.get("run_id") and job.get("upload_id"):
                set_run(sb, job["run_id"], "failed", msg[:1000])
                set_upload(sb, job["upload_id"], "failed", msg[:1000])
                log_run(sb, job["run_id"], "error", "failed", message=msg[:1000])

            time.sleep(1)

        time.sleep(0.1)


if __name__ == "__main__":
    main()