# ============================================================
# File: api/admin_uploads.py
# JWT-only admin routes (Supabase Auth)
# ============================================================
from __future__ import annotations

import hashlib
import os, re
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from .supabase_client import get_supabase
from .auth import require_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_EXT = {".csv", ".xlsx"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_uploadfile_md5_and_bytes(upload: UploadFile, chunk_size: int = 1024 * 1024) -> tuple[str, bytes]:
    md5 = hashlib.md5()
    buf = bytearray()
    while True:
        chunk = upload.file.read(chunk_size)
        if not chunk:
            break
        md5.update(chunk)
        buf.extend(chunk)
    return md5.hexdigest(), bytes(buf)


def _infer_ext(filename: str) -> str:
    dot = filename.lower().rfind(".")
    return filename[dot:] if dot >= 0 else ""


def _canon_col(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _pick_col(df: pd.DataFrame, aliases: list[str], field_name: str) -> str:
    canon_to_orig = {_canon_col(c): c for c in df.columns}
    for a in aliases:
        key = _canon_col(a)
        if key in canon_to_orig:
            return canon_to_orig[key]
    raise HTTPException(
        status_code=400,
        detail=f"Missing required field '{field_name}'. Acceptable: {aliases}. Found: {list(df.columns)}",
    )


def _parse_date_series(df: pd.DataFrame, col: str, *, field_name: str, allow_all_missing: bool) -> pd.Series:
    s = pd.to_datetime(df[col], errors="coerce")
    if allow_all_missing and s.isna().all():
        return s
    if (not allow_all_missing) and s.isna().all():
        raise HTTPException(status_code=400, detail=f"Field '{field_name}' (column '{col}') is not parseable as dates")
    return s


def _quick_validate_headers(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().split(".")[-1]
    if ext == "csv":
        df = pd.read_csv(pd.io.common.BytesIO(file_bytes), low_memory=False)
    elif ext == "xlsx":
        df = pd.read_excel(pd.io.common.BytesIO(file_bytes))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type (use .csv or .xlsx)")

    CASE_ID_ALIASES = ["CASE ID", "Case ID", "case_id", "caseid", "case number", "caseno", "id"]
    ONSET_ALIASES = ["DOnset", "Donset", "Date Onset", "Date of Onset", "Onset", "OnsetDate", "DateOnset", "date_onset"]
    DOB_ALIASES = ["DOB", "Dob", "Date of Birth", "Birth Date", "Birthdate", "BDate", "date_of_birth", "birth_date"]
    SEX_ALIASES = ["Sex", "sex", "Gender", "gender", "M/F", "MF", "Male/Female"]
    BARANGAY_ALIASES = [
        "Barangay",
        "(Current Address) Barangay",
        "Current Address Barangay",
        "Barangay (address)",
        "Address Barangay",
        "Current Address",
        "Residence Barangay",
        "Brgy",
        "Brgy.",
    ]

    case_id_col = _pick_col(df, CASE_ID_ALIASES, "case_id")
    onset_col = _pick_col(df, ONSET_ALIASES, "donset")
    dob_col = _pick_col(df, DOB_ALIASES, "dob")
    sex_col = _pick_col(df, SEX_ALIASES, "sex")
    barangay_col = _pick_col(df, BARANGAY_ALIASES, "barangay")

    df[case_id_col] = df[case_id_col].astype("string")

    onset = _parse_date_series(df, onset_col, field_name="DOnset", allow_all_missing=False)
    dob = _parse_date_series(df, dob_col, field_name="DOB", allow_all_missing=True)

    min_onset = onset.min()
    max_onset = onset.max()

    def to_week_start(dt: pd.Timestamp) -> pd.Timestamp:
        if pd.isna(dt):
            return pd.NaT
        return (dt - pd.Timedelta(days=int(dt.weekday()))).normalize()

    min_week = to_week_start(min_onset) if pd.notna(min_onset) else None
    max_week = to_week_start(max_onset) if pd.notna(max_onset) else None

    today = pd.Timestamp.now().normalize()
    if pd.notna(max_onset) and max_onset.normalize() > today:
        raise HTTPException(status_code=400, detail="DOnset contains future dates")

    dob_after_onset_count = 0
    dob_after_onset_sample = []
    if dob.notna().any() and onset.notna().any():
        both = dob.notna() & onset.notna()
        if both.any():
            bad = (dob[both] > onset[both])
            dob_after_onset_count = int(bad.sum())
            if dob_after_onset_count > 0:
                dob_after_onset_sample = bad[bad].index[:5].tolist()

    if df[barangay_col].isna().all():
        raise HTTPException(status_code=400, detail=f"Barangay column '{barangay_col}' is empty")

    return {
        "rows_count": int(len(df)),
        "min_onset_date": min_onset.date().isoformat() if pd.notna(min_onset) else None,
        "max_onset_date": max_onset.date().isoformat() if pd.notna(max_onset) else None,
        "min_week_start": min_week.date().isoformat() if min_week is not None and pd.notna(min_week) else None,
        "max_week_start": max_week.date().isoformat() if max_week is not None and pd.notna(max_week) else None,
        "warnings": {
            "dob_after_onset_count": dob_after_onset_count,
            "dob_after_onset_sample_rows": dob_after_onset_sample,
        },
        "matched_columns": {
            "case_id": case_id_col,
            "donset": onset_col,
            "dob": dob_col,
            "sex": sex_col,
            "barangay": barangay_col,
        },
    }


@router.post("/login")
def admin_login(user_id: str = Depends(require_admin_user)):
    return {"ok": True, "user_id": user_id}


@router.post("/uploads")
def admin_upload(
    file: UploadFile = File(...),
    force: bool = Query(False, description="Force a new run even if the same file was already processed"),
    user_id: str = Depends(require_admin_user),
):
    sb = get_supabase()
    bucket = os.getenv("UPLOAD_BUCKET", "dengue-uploads")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = _infer_ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    file_md5, file_bytes = _hash_uploadfile_md5_and_bytes(file)

    existing = (
        sb.table("upload_runs")
        .select("upload_id, run_id, status, storage_path, original_filename, created_at, file_md5")
        .eq("file_md5", file_md5)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []

    if existing:
        row = existing[0]
        st = row.get("status")

        # 1) Active job exists => idempotent (don’t enqueue duplicates)
        if st in ("queued", "running"):
            return {"idempotent": True, "reason": "already_active", **row}

        # 2) Already succeeded and not forcing => return info, do not create new run
        if st == "succeeded" and not force:
            return {"idempotent": True, "reason": "already_succeeded", **row}

        # else: failed/canceled/deleted OR force=true => proceed to create new upload
    meta = _quick_validate_headers(file_bytes, file.filename)

    upload_id = str(uuid4())
    run_id = str(uuid4())

    day = datetime.now(timezone.utc).date().isoformat()
    storage_path = f"uploads/{day}/{upload_id}/{file.filename}"

    # upload
    storage = sb.storage.from_(bucket)
    up = storage.upload(
        storage_path,
        file_bytes,
        file_options={"content-type": file.content_type or "application/octet-stream"},
    )
    if isinstance(up, dict) and up.get("error"):
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {up['error']}")
    if hasattr(up, "error") and up.error:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {up.error}")

    # runs row
    sb.table("runs").insert(
        {
            "run_id": run_id,
            "mode": "production",
            "run_kind": "production",
            "status": "queued",
            "horizon_weeks": 12,
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "error_message": None,
            "created_by": user_id,   # ✅ add this
        }
    ).execute()

    # upload_runs row (store who uploaded)
    sb.table("upload_runs").insert(
        {
            "upload_id": upload_id,
            "user_id": user_id,
            "storage_path": storage_path,
            "original_filename": file.filename,
            "file_md5": file_md5,
            "run_id": run_id,
            "status": "queued",
            "rows_count": meta["rows_count"],
            "min_onset_date": meta["min_onset_date"],
            "max_onset_date": meta["max_onset_date"],
            "min_week_start": meta["min_week_start"],
            "max_week_start": meta["max_week_start"],
            "error_message": None,
        }
    ).execute()

    return {
        "idempotent": False,
        "upload_id": upload_id,
        "run_id": run_id,
        "status": "queued",
        "storage_path": storage_path,
        "file_md5": file_md5,
        "user_id": user_id,
        **meta,
    }


@router.get("/upload-runs")
def list_upload_runs(
    limit: int = Query(50, ge=1, le=500),
    user_id: str = Depends(require_admin_user),
):
    sb = get_supabase()
    rows = (
        sb.table("upload_runs_with_uploader")
        .select(
            "upload_id, created_at, original_filename, file_md5, storage_path, run_id, status, "
            "error_message, rows_count, min_onset_date, max_onset_date, min_week_start, max_week_start, "
            "user_id, first_name, last_name, association"
        )
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []
    return {"uploads": rows}


@router.post("/uploads/{upload_id}/cancel")
def cancel_upload(
    upload_id: str,
    user_id: str = Depends(require_admin_user),
):
    sb = get_supabase()

    rows = (
        sb.table("upload_runs")
        .select("upload_id,status")
        .eq("upload_id", upload_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not rows:
        raise HTTPException(status_code=404, detail="upload not found")

    st = rows[0]["status"]
    if st in ("succeeded", "failed", "deleted", "canceled"):
        return {"ok": True, "status": st}

    sb.table("upload_runs").update(
        {"status": "canceled", "canceled_at": _utc_now_iso(), "canceled_by": user_id}
    ).eq("upload_id", upload_id).execute()

    return {"ok": True, "status": "canceled"}


@router.delete("/uploads/{upload_id}")
def delete_upload(
    upload_id: str,
    user_id: str = Depends(require_admin_user),
):
    sb = get_supabase()
    bucket = os.getenv("UPLOAD_BUCKET", "dengue-uploads")

    rows = (
        sb.table("upload_runs")
        .select("upload_id,status,storage_path")
        .eq("upload_id", upload_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not rows:
        raise HTTPException(status_code=404, detail="upload not found")

    st = rows[0]["status"]
    path = rows[0]["storage_path"]

    if st == "running":
        raise HTTPException(status_code=400, detail="Cannot delete while running. Cancel first.")

    # attempt storage removal
    try:
        sb.storage.from_(bucket).remove([path])
    except Exception:
        pass

    sb.table("upload_runs").update(
        {"status": "deleted", "deleted_at": _utc_now_iso(), "deleted_by": user_id}
    ).eq("upload_id", upload_id).execute()

    return {"ok": True, "status": "deleted"}