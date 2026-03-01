# ============================================================
# file: denguard/export_supabase.py
# Export run-scoped artifacts to Supabase.
# ============================================================
from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

from denguard.normalize import normalize_barangay_name

load_dotenv()


def _load_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_df(sb: Client, table: str, df: pd.DataFrame, conflict: str, chunk_size: int = 500) -> None:
    if df.empty:
        print(f"Skipped {table}: empty dataframe.")
        return

    records = df.to_dict(orient="records")
    total = len(records)
    batches = math.ceil(total / chunk_size)

    for i in range(batches):
        batch = records[i * chunk_size : (i + 1) * chunk_size]
        sb.table(table).upsert(batch, on_conflict=conflict).execute()

    print(f"Upserted {total} rows into {table}")


def mark_run(sb: Client, run_id: str, status: str, error_message: str | None = None) -> None:
    payload: dict[str, object] = {"status": status}

    if status in ("running", "queued"):
        payload["started_at"] = _utc_now_iso()
        payload["finished_at"] = None
        payload["error_message"] = None

    if status in ("succeeded", "failed"):
        payload["finished_at"] = _utc_now_iso()
        payload["error_message"] = error_message or None

    sb.table("runs").update(payload).eq("run_id", run_id).execute()


def upsert_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "mode", "train_end", "horizon_weeks"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"runs missing required columns: {sorted(missing)}")

    for c in ["data_version", "code_version", "run_kind", "status", "started_at", "finished_at", "error_message"]:
        if c not in df.columns:
            df[c] = None

    cols = [
        "run_id",
        "mode",
        "train_end",
        "horizon_weeks",
        "data_version",
        "code_version",
        "run_kind",
        "status",
        "started_at",
        "finished_at",
        "error_message",
    ]
    _upsert_df(sb, "runs", df[cols].copy(), conflict="run_id")


def upsert_barangays(sb: Client, df: pd.DataFrame) -> None:
    required = {"name", "display_name"}
    if not required.issubset(df.columns):
        raise ValueError(f"barangays requires columns: {sorted(required)}")
    _upsert_df(sb, "barangays", df[["name", "display_name"]].copy(), conflict="name")


def upsert_city_forecasts_long(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "week_start", "model_name", "yhat", "horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"city_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id", "week_start", "model_name", "yhat", "yhat_lower", "yhat_upper", "horizon_type"]
    for c in cols:
        if c not in df.columns:
            df[c] = None

    _upsert_df(sb, "city_forecasts_long", df[cols].copy(), conflict="run_id,week_start,model_name,horizon_type")


def upsert_barangay_forecasts_long(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "name", "week_start", "model_name", "yhat", "horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"barangay_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id", "name", "week_start", "model_name", "yhat", "yhat_lower", "yhat_upper", "horizon_type", "status"]
    for c in cols:
        if c not in df.columns:
            df[c] = None

    _upsert_df(sb, "barangay_forecasts_long", df[cols].copy(), conflict="run_id,name,week_start,model_name,horizon_type")


def upsert_city_weekly_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "week_start", "city_cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"city_weekly_runs missing required columns: {sorted(missing)}")

    _upsert_df(sb, "city_weekly_runs", df[["run_id", "week_start", "city_cases"]].copy(), conflict="run_id,week_start")


def upsert_barangay_weekly_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "name", "week_start", "cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"barangay_weekly_runs missing required columns: {sorted(missing)}")

    _upsert_df(sb, "barangay_weekly_runs", df[["run_id", "name", "week_start", "cases"]].copy(), conflict="run_id,name,week_start")


def upload_to_supabase(cfg) -> None:
    """
    Export-only.
    Ensures the parent runs row exists and tracks status across the export.
    """
    sb = _load_supabase()
    outdir = cfg.out
    run_id = cfg.run_id
    if not run_id:
        raise RuntimeError("cfg.run_id is missing")

    run_kind = getattr(cfg, "run_kind", "production")

    horizon_weeks = 0
    future_candidates = [
        outdir / "barangay_forecasts_all_models_future_long.csv",
        outdir / "barangay_forecasts_long_future.csv",
        outdir / "barangay_forecasts_long.csv",
        outdir / "city_forecasts_future.csv",
    ]
    for p in future_candidates:
        if not p.exists():
            continue
        tmp = pd.read_csv(p)
        if tmp.empty:
            continue
        col = "ds" if "ds" in tmp.columns else "week_start"
        if col not in tmp.columns:
            continue
        horizon_weeks = int(pd.to_datetime(tmp[col], errors="coerce").dt.date.nunique())
        if horizon_weeks > 0:
            break

    train_end_value = getattr(cfg, "backtest_end_date", None) if run_kind == "backtest" else None
    runs_df = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "mode": cfg.incoming_mode,
                "train_end": train_end_value,
                "horizon_weeks": horizon_weeks,
                "data_version": None,
                "code_version": None,
                "run_kind": run_kind,
                "status": "running",
                "started_at": getattr(cfg, "run_started_at_utc", None) or _utc_now_iso(),
                "finished_at": None,
                "error_message": None,
            }
        ]
    )
    upsert_runs(sb, runs_df)
    mark_run(sb, run_id, "running")

    try:
        weekly_path = outdir / "weekly_cases_all_barangays.csv"
        if not weekly_path.exists():
            raise FileNotFoundError(f"Missing required file: {weekly_path}")

        src_bg = pd.read_csv(weekly_path)["Barangay_key"].drop_duplicates()
        df_barangays = pd.DataFrame({"name": src_bg.apply(normalize_barangay_name), "display_name": src_bg})
        upsert_barangays(sb, df_barangays)

        city_long_path = outdir / "city_forecasts_long.csv"
        if city_long_path.exists():
            city_long = pd.read_csv(city_long_path)
            if "run_id" not in city_long.columns:
                city_long["run_id"] = run_id
            city_long["week_start"] = pd.to_datetime(city_long["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
            if "model_name" not in city_long.columns:
                city_long["model_name"] = "preferred"
            if "horizon_type" not in city_long.columns:
                city_long["horizon_type"] = "future"
            upsert_city_forecasts_long(sb, city_long)
        else:
            print("Skipped city_forecasts_long: city_forecasts_long.csv not found.")

        bg_long_path = outdir / "barangay_forecasts_long.csv"
        future_only_path = outdir / "barangay_forecasts_all_models_future_long.csv"
        chosen_bg_path = bg_long_path if bg_long_path.exists() else future_only_path

        if chosen_bg_path.exists():
            bg_long = pd.read_csv(chosen_bg_path)
            if "Barangay_key" in bg_long.columns:
                bg_long = bg_long.rename(columns={"Barangay_key": "name"})
            if "ds" in bg_long.columns:
                bg_long = bg_long.rename(columns={"ds": "week_start"})

            bg_long["run_id"] = run_id
            bg_long["name"] = bg_long["name"].apply(normalize_barangay_name)
            bg_long["week_start"] = pd.to_datetime(bg_long["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
            if "horizon_type" not in bg_long.columns:
                bg_long["horizon_type"] = "future"
            upsert_barangay_forecasts_long(sb, bg_long)
        else:
            print("Skipped barangay_forecasts_long: no long CSV found.")

        city_weekly_path = outdir / "city_weekly.csv"
        if city_weekly_path.exists():
            df_city_weekly = pd.read_csv(city_weekly_path).rename(columns={"WeekStart": "week_start", "CityCases": "city_cases"})
            df_city_weekly["run_id"] = run_id
            df_city_weekly["city_cases"] = pd.to_numeric(df_city_weekly["city_cases"], errors="coerce").fillna(0).astype(int)
            df_city_weekly["week_start"] = pd.to_datetime(df_city_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
            upsert_city_weekly_runs(sb, df_city_weekly)
        else:
            print("Skipped city_weekly_runs: city_weekly.csv not found.")

        df_bg_weekly = pd.read_csv(weekly_path).rename(columns={"Barangay_key": "name", "WeekStart": "week_start", "Cases": "cases"})
        df_bg_weekly["run_id"] = run_id
        df_bg_weekly["name"] = df_bg_weekly["name"].apply(normalize_barangay_name)
        df_bg_weekly["cases"] = pd.to_numeric(df_bg_weekly["cases"], errors="coerce").fillna(0).astype(int)
        df_bg_weekly["week_start"] = pd.to_datetime(df_bg_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
        upsert_barangay_weekly_runs(sb, df_bg_weekly)

        mark_run(sb, run_id, "succeeded")
        print("Supabase export complete.")
    except Exception as e:
        mark_run(sb, run_id, "failed", error_message=str(e))
        raise


if __name__ == "__main__":
    from denguard.config import DEFAULT_CFG

    upload_to_supabase(DEFAULT_CFG)
