# ============================================================
# File: api/admin_uploads.py
# NEW: Admin upload endpoint + logs endpoint (temporary token auth)
# ============================================================
from __future__ import annotations

import hashlib
import os, re
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Header, HTTPException, Query
from .supabase_client import get_supabase

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_EXT = {".csv", ".xlsx"}


def _require_admin_token(x_admin_token: str | None) -> None:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise RuntimeError("ADMIN_TOKEN is not set in environment")
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_uploadfile_md5_and_bytes(upload: UploadFile, chunk_size: int = 1024 * 1024) -> tuple[str, bytes]:
    """
    Simple MVP: buffers file in memory.
    If uploads can be huge, switch to disk streaming.
    """
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
    """
    Canonicalize column names for matching.
    Example: '(Current Address) Barangay' -> 'currentaddressbarangay'
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _pick_col(df: pd.DataFrame, aliases: list[str], field_name: str) -> str:
    """
    Find the first matching column in df using canonical matching.
    Returns the original df column name.
    """
    canon_to_orig = {_canon_col(c): c for c in df.columns}

    # also allow direct canonical matches (e.g., user writes already-canonical headers)
    for a in aliases:
        key = _canon_col(a)
        if key in canon_to_orig:
            return canon_to_orig[key]

    raise HTTPException(
        status_code=400,
        detail=(
            f"Missing required field '{field_name}'. "
            f"Acceptable columns include: {aliases}. "
            f"Found columns: {list(df.columns)}"
        ),
    )


def _parse_date_series(df: pd.DataFrame, col: str, *, field_name: str, allow_all_missing: bool) -> pd.Series:
    s = pd.to_datetime(df[col], errors="coerce")
    if allow_all_missing and s.isna().all():
        return s
    if not allow_all_missing and s.isna().all():
        raise HTTPException(status_code=400, detail=f"Field '{field_name}' (column '{col}') is not parseable as dates")
    return s


def _quick_validate_headers(file_bytes: bytes, filename: str) -> dict:
    """
    Flexible MVP validation:
      - accepts alias column names
      - validates required fields exist
      - validates DOnset and DOB parseability
      - computes metadata for upload_runs
    """
    ext = filename.lower().split(".")[-1]
    if ext == "csv":
        df = pd.read_csv(pd.io.common.BytesIO(file_bytes), low_memory=False)
    elif ext == "xlsx":
        df = pd.read_excel(pd.io.common.BytesIO(file_bytes))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type (use .csv or .xlsx)")

    # ----------------------------
    # Aliases (add anytime)
    # ----------------------------
    CASE_ID_ALIASES = [
        "CASE ID", "Case ID", "case_id", "caseid", "case no", "case number", "caseno", "id",
    ]
    ONSET_ALIASES = [
        "DOnset", "Donset", "Date Onset", "Date of Onset", "Onset", "OnsetDate", "DateOnset", "date_onset",
    ]
    DOB_ALIASES = [
        "DOB", "Dob", "Date of Birth", "Birth Date", "Birthdate", "BDate", "date_of_birth", "birth_date",
    ]
    SEX_ALIASES = [
        "Sex", "sex", "Gender", "gender", "M/F", "MF", "Male/Female",
    ]
    BARANGAY_ALIASES = [
        "Barangay",
        "(Current Address) Barangay",
        "Current Address Barangay",
        "Barangay (address)",
        "Address Barangay",
        "Current Address",
        "current address",
        "Residence Barangay",
        "Brgy",
        "Brgy.",
    ]

    case_id_col = _pick_col(df, CASE_ID_ALIASES, "case_id")
    onset_col = _pick_col(df, ONSET_ALIASES, "donset")
    dob_col = _pick_col(df, DOB_ALIASES, "dob")
    sex_col = _pick_col(df, SEX_ALIASES, "sex")
    barangay_col = _pick_col(df, BARANGAY_ALIASES, "barangay")

    # Normalize basics
    df[case_id_col] = df[case_id_col].astype("string")

    # Parse dates
    onset = _parse_date_series(df, onset_col, field_name="DOnset", allow_all_missing=False)
    dob = _parse_date_series(df, dob_col, field_name="DOB", allow_all_missing=True)

    min_onset = onset.min()
    max_onset = onset.max()

    # W-MON week_start: onset - weekday (Mon=0)
    def to_week_start(dt: pd.Timestamp) -> pd.Timestamp:
        if pd.isna(dt):
            return pd.NaT
        return (dt - pd.Timedelta(days=int(dt.weekday()))).normalize()

    min_week = to_week_start(min_onset) if pd.notna(min_onset) else None
    max_week = to_week_start(max_onset) if pd.notna(max_onset) else None

    # Simple sanity checks
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
                # sample up to 5 row indices (original df indices)
                dob_after_onset_sample = bad[bad].index[:5].tolist()

    # Barangay presence check
    if df[barangay_col].isna().all():
        raise HTTPException(status_code=400, detail=f"Barangay column '{barangay_col}' is empty")

    # Sex presence check (allow missing values, but column must exist)
    # Optional: normalize sex values later in pipeline

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
@router.post("/uploads")
def admin_upload(
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None),
):
    """
    Creates upload_runs + runs (queued) and stores file in Supabase Storage.
    Idempotent by file_md5:
      - if same file already exists: return existing row (no new run).
    """
    _require_admin_token(x_admin_token)

    sb = get_supabase()
    bucket = os.getenv("UPLOAD_BUCKET", "dengue-uploads")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = _infer_ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    file_md5, file_bytes = _hash_uploadfile_md5_and_bytes(file)

    # idempotency: return existing upload if md5 exists
    existing = (
        sb.table("upload_runs")
        .select("upload_id, run_id, status, storage_path, original_filename, created_at, file_md5")
        .eq("file_md5", file_md5)
        .limit(1)
        .execute()
        .data
    ) or []
    if existing:
        row = existing[0]
        return {"idempotent": True, **row}

    meta = _quick_validate_headers(file_bytes, file.filename)

    upload_id = str(uuid4())
    run_id = str(uuid4())

    day = datetime.now(timezone.utc).date().isoformat()
    storage_path = f"uploads/{day}/{upload_id}/{file.filename}"

    try:
        # upload to storage (supabase-py versions differ; try the most common signature)
        storage = sb.storage.from_(bucket)
        up = storage.upload(
            storage_path,
            file_bytes,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )

        # Some versions return dict-like objects
        if isinstance(up, dict) and up.get("error"):
            raise RuntimeError(f"Storage upload failed: {up['error']}")
        if hasattr(up, "error") and up.error:
            raise RuntimeError(f"Storage upload failed: {up.error}")

        # create runs row (queued)
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
            }
        ).execute()

        # create upload_runs row (queued)
        sb.table("upload_runs").insert(
            {
                "upload_id": upload_id,
                "user_id": None,
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

    except Exception as e:
        # This is the key: you'll now see the real reason in the HTTP response + logs
        raise HTTPException(status_code=500, detail=f"Upload failed: {type(e).__name__}: {e}")

    return {
        "idempotent": False,
        "upload_id": upload_id,
        "run_id": run_id,
        "status": "queued",
        "storage_path": storage_path,
        "file_md5": file_md5,
        **meta,
    }


@router.get("/upload-runs")
def list_upload_runs(
    limit: int = Query(50, ge=1, le=500),
    x_admin_token: str | None = Header(default=None),
):
    """
    Admin Upload Logs UI data source.
    """
    _require_admin_token(x_admin_token)

    sb = get_supabase()
    rows = (
        sb.table("upload_runs")
        .select(
            "upload_id, created_at, original_filename, file_md5, storage_path, run_id, status, "
            "error_message, rows_count, min_onset_date, max_onset_date, min_week_start, max_week_start"
        )
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []
    return {"uploads": rows}