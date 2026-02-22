# ============================================================
# file: denguard/export_supabase.py
# PATCH: stop managing runs status here; export run-scoped weekly
# ============================================================
from __future__ import annotations

import os
import math
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

from denguard.normalize import normalize_barangay_name

load_dotenv()


def _load_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role only
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _upsert_df(sb: Client, table: str, df: pd.DataFrame, conflict: str, chunk_size: int = 500) -> None:
    if df.empty:
        print(f"ℹ️ Skipped {table}: empty dataframe.")
        return

    records = df.to_dict(orient="records")
    total = len(records)
    batches = math.ceil(total / chunk_size)

    for i in range(batches):
        batch = records[i * chunk_size : (i + 1) * chunk_size]
        sb.table(table).upsert(batch, on_conflict=conflict).execute()

    print(f"✅ Upserted {total} rows into {table}")


def upsert_barangays(sb: Client, df: pd.DataFrame) -> None:
    required = {"name", "display_name"}
    if not required.issubset(df.columns):
        raise ValueError(f"barangays requires columns: {sorted(required)}")
    df = df[["name", "display_name"]].copy()
    _upsert_df(sb, "barangays", df, conflict="name")


def upsert_city_forecasts_long(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "week_start", "model_name", "yhat", "horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"city_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id", "week_start", "model_name", "yhat", "yhat_lower", "yhat_upper", "horizon_type"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    _upsert_df(sb, "city_forecasts_long", df, conflict="run_id,week_start,model_name,horizon_type")


def upsert_barangay_forecasts_long(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "name", "week_start", "model_name", "yhat", "horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"barangay_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id", "name", "week_start", "model_name", "yhat", "yhat_lower", "yhat_upper", "horizon_type", "status"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    _upsert_df(sb, "barangay_forecasts_long", df, conflict="run_id,name,week_start,model_name,horizon_type")


# ✅ NEW: run-scoped weekly actuals (safe publish)
def upsert_city_weekly_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "week_start", "city_cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"city_weekly_runs missing required columns: {sorted(missing)}")

    df = df[["run_id", "week_start", "city_cases"]].copy()
    _upsert_df(sb, "city_weekly_runs", df, conflict="run_id,week_start")


def upsert_barangay_weekly_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "name", "week_start", "cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"barangay_weekly_runs missing required columns: {sorted(missing)}")

    df = df[["run_id", "name", "week_start", "cases"]].copy()
    _upsert_df(sb, "barangay_weekly_runs", df, conflict="run_id,name,week_start")


def upload_to_supabase(cfg) -> None:
    """
    Export-only. Does NOT create or mark runs.
    Worker owns:
      - runs.status transitions
      - publish active_runs pointer
      - upload_runs status updates
    """
    sb = _load_supabase()
    outdir = cfg.out
    run_id = cfg.run_id
    if not run_id:
        raise RuntimeError("cfg.run_id is missing")

    # ---------------------------------------------------------
    # 1) BARANGAYS FIRST (FK requirement)
    # ---------------------------------------------------------
    weekly_path = outdir / "weekly_cases_all_barangays.csv"
    if not weekly_path.exists():
        raise FileNotFoundError(f"Missing required file: {weekly_path}")

    src_bg = pd.read_csv(weekly_path)["Barangay_key"].drop_duplicates()
    df_barangays = pd.DataFrame({"name": src_bg.apply(normalize_barangay_name), "display_name": src_bg})
    upsert_barangays(sb, df_barangays)

    # ---------------------------------------------------------
    # 2) CITY FORECASTS LONG
    # ---------------------------------------------------------
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
        print("ℹ️ Skipped city_forecasts_long: city_forecasts_long.csv not found.")

    # ---------------------------------------------------------
    # 3) BARANGAY FORECASTS LONG
    # ---------------------------------------------------------
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
        print("ℹ️ Skipped barangay_forecasts_long: no long CSV found.")

    # ---------------------------------------------------------
    # 4) CITY WEEKLY (RUN-SCOPED)
    # ---------------------------------------------------------
    city_weekly_path = outdir / "city_weekly.csv"
    if city_weekly_path.exists():
        df_city_weekly = pd.read_csv(city_weekly_path).rename(
            columns={"WeekStart": "week_start", "CityCases": "city_cases"}
        )
        df_city_weekly["run_id"] = run_id
        df_city_weekly["city_cases"] = pd.to_numeric(df_city_weekly["city_cases"], errors="coerce").fillna(0).astype(int)
        df_city_weekly["week_start"] = pd.to_datetime(df_city_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
        upsert_city_weekly_runs(sb, df_city_weekly)
    else:
        print("ℹ️ Skipped city_weekly_runs: city_weekly.csv not found.")

    # ---------------------------------------------------------
    # 5) BARANGAY WEEKLY (RUN-SCOPED)
    # ---------------------------------------------------------
    df_bg_weekly = pd.read_csv(weekly_path).rename(
        columns={"Barangay_key": "name", "WeekStart": "week_start", "Cases": "cases"}
    )
    df_bg_weekly["run_id"] = run_id
    df_bg_weekly["name"] = df_bg_weekly["name"].apply(normalize_barangay_name)
    df_bg_weekly["cases"] = pd.to_numeric(df_bg_weekly["cases"], errors="coerce").fillna(0).astype(int)
    df_bg_weekly["week_start"] = pd.to_datetime(df_bg_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
    upsert_barangay_weekly_runs(sb, df_bg_weekly)

    print("✅ Supabase export: COMPLETE (export-only)")


if __name__ == "__main__":
    from denguard.config import DEFAULT_CFG
    upload_to_supabase(DEFAULT_CFG)