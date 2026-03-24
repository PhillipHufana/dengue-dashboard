from __future__ import annotations

import os
import tempfile
import time
import traceback
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from api.supabase_client import get_supabase
from denguard.config import DEFAULT_CFG
from denguard.export_supabase import mark_run
from denguard.pipeline import run_production

load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_master_csv() -> Path:
    return _base_dir() / "intermediate" / "dengue_master_cleaned.csv"


def _default_out_root() -> Path:
    return _base_dir() / "intermediate" / "runs"


def _default_policy_csv() -> Path:
    return _base_dir() / "policies" / "local_model_performance_backtest_2022-12-26_3b3037b5.csv"


def _get_bucket() -> str:
    return os.getenv("UPLOAD_BUCKET", "dengue-uploads")


def _update_upload_status(sb, upload_id: str, *, status: str, error_message: str | None = None) -> None:
    payload = {
        "status": status,
        "error_message": error_message,
    }
    if status == "running":
        payload["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if status in {"succeeded", "failed"}:
        payload["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sb.table("upload_runs").update(payload).eq("upload_id", upload_id).execute()


def _claim_next_upload(sb):
    rows = (
        sb.table("upload_runs")
        .select("upload_id, run_id, storage_path, original_filename, status, created_at")
        .eq("status", "queued")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    ) or []
    if not rows:
        return None
    row = rows[0]
    _update_upload_status(sb, row["upload_id"], status="running")
    mark_run(sb, row["run_id"], "running")
    return row


def _download_upload_bytes(sb, storage_path: str) -> bytes:
    data = sb.storage.from_(_get_bucket()).download(storage_path)
    if not data:
        raise RuntimeError(f"Downloaded empty payload for {storage_path}")
    return data


def _build_worker_cfg(*, run_id: str, incoming_folder: Path, out_dir: Path):
    master_csv = Path(os.getenv("DENGUARD_MASTER_DATA_CSV", str(_default_master_csv()))).resolve()
    policy_csv = Path(os.getenv("DENGUARD_POLICY_LOCAL_PERF_CSV", str(_default_policy_csv()))).resolve()
    canon_csv = os.getenv("DENGUARD_CANON_CSV", "")
    incoming_mode = os.getenv("DENGUARD_INCOMING_MODE", "incremental").strip().lower() or "incremental"

    return replace(
        DEFAULT_CFG,
        run_id=run_id,
        run_kind="production",
        incoming_mode=incoming_mode,
        incoming_folder=str(incoming_folder),
        out_dir=str(out_dir),
        master_data_csv=str(master_csv),
        raw_xlsx="",
        canon_csv=str(canon_csv),
        policy_local_perf_csv=str(policy_csv),
    )


def process_upload(sb, upload_row) -> None:
    upload_id = str(upload_row["upload_id"])
    run_id = str(upload_row["run_id"])
    storage_path = str(upload_row["storage_path"])
    filename = str(upload_row.get("original_filename") or Path(storage_path).name)

    with tempfile.TemporaryDirectory(prefix=f"denguard-upload-{upload_id}-") as tmpdir:
        tmp = Path(tmpdir)
        incoming_dir = tmp / "incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)

        payload = _download_upload_bytes(sb, storage_path)
        local_upload = incoming_dir / filename
        local_upload.write_bytes(payload)

        out_root = Path(os.getenv("DENGUARD_OUT_ROOT", str(_default_out_root()))).resolve()
        out_dir = out_root / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        cfg = _build_worker_cfg(run_id=run_id, incoming_folder=incoming_dir, out_dir=out_dir)
        run_production(cfg)

    _update_upload_status(sb, upload_id, status="succeeded", error_message=None)


def worker_loop() -> None:
    sb = get_supabase()
    poll_seconds = _env_int("WORKER_POLL_SECONDS", 15)
    run_once = _env_bool("WORKER_RUN_ONCE", False)

    print(f"Worker started. Poll interval: {poll_seconds}s")

    while True:
        claimed = None
        try:
            claimed = _claim_next_upload(sb)
            if claimed:
                print(f"Processing upload {claimed['upload_id']} for run {claimed['run_id']}")
                process_upload(sb, claimed)
                print(f"Completed upload {claimed['upload_id']}")
            elif run_once:
                print("No queued uploads found.")
                return
        except Exception as exc:
            traceback.print_exc()
            if claimed:
                upload_id = str(claimed["upload_id"])
                run_id = str(claimed["run_id"])
                _update_upload_status(sb, upload_id, status="failed", error_message=str(exc))
                mark_run(sb, run_id, "failed", error_message=str(exc))
        if run_once:
            return
        time.sleep(poll_seconds)


if __name__ == "__main__":
    worker_loop()
