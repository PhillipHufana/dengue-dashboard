# file: denguard/export_supabase.py
from __future__ import annotations

import os
import math
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

from denguard.normalize import normalize_barangay_name
from datetime import datetime, timezone
load_dotenv()

# ============================================================
# INTERNAL: Create Supabase Client
# ============================================================


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def mark_run(sb: Client, run_id: str, status: str, error_message: str | None = None):
    payload = {"status": status}

    if status in ("running", "queued"):
        payload["started_at"] = _utc_now_iso()
        payload["finished_at"] = None
        payload["error_message"] = None

    if status in ("succeeded", "failed"):
        payload["finished_at"] = _utc_now_iso()
        payload["error_message"] = (error_message or None)

    sb.table("runs").update(payload).eq("run_id", run_id).execute()

def _load_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Must be service role
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials not found. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    return create_client(url, key)


# ============================================================
# INTERNAL: Batch UPSERT Helper
# ============================================================

def _upsert_df(sb: Client, table: str, df: pd.DataFrame, conflict: str, chunk_size: int = 500) -> None:
    if df.empty:
        print(f"ℹ️ Skipped {table}: empty dataframe.")
        return

    records = df.to_dict(orient="records")

    total = len(records)
    batches = math.ceil(total / chunk_size)

    for i in range(batches):
        batch = records[i * chunk_size:(i + 1) * chunk_size]
        sb.table(table).upsert(batch, on_conflict=conflict).execute()

    print(f"✅ Upserted {total} rows into {table}")

# ============================================================
# PUBLIC UPSERT FUNCTIONS (SAFE: subset to table columns)
# ============================================================
def upsert_runs(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id", "mode", "train_end", "horizon_weeks"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"runs missing required columns: {sorted(missing)}")

    # optional columns now supported by table
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
    df = df[cols].copy()

    _upsert_df(sb, "runs", df, conflict="run_id")


def upsert_barangays(sb: Client, df: pd.DataFrame) -> None:
    required = {"name", "display_name"}
    if not required.issubset(df.columns):
        raise ValueError(f"barangays requires columns: {sorted(required)}")
    # Only send columns that exist in your Supabase table schema
    df = df[["name", "display_name"]].copy()
    _upsert_df(sb, "barangays", df, conflict="name")


def upsert_city_forecasts_long(sb: Client,df: pd.DataFrame) -> None:
    required = {"run_id","week_start","model_name","yhat","horizon_type"}
    missing = required - set(df.columns)
    if missing:
       raise ValueError(f"city_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id","week_start","model_name","yhat","yhat_lower","yhat_upper","horizon_type"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    _upsert_df(
        sb,
        "city_forecasts_long",
        df,
        conflict="run_id,week_start,model_name,horizon_type"
    )


def upsert_barangay_forecasts_long(sb: Client, df: pd.DataFrame) -> None:
    required = {"run_id","name","week_start","model_name","yhat","horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"barangay_forecasts_long missing required columns: {sorted(missing)}")

    cols = ["run_id","name","week_start","model_name","yhat","yhat_lower","yhat_upper","horizon_type","status"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    _upsert_df(
        sb,
        "barangay_forecasts_long",
        df,
        conflict="run_id,name,week_start,model_name,horizon_type"
    )


def upsert_city_weekly(sb: Client, df: pd.DataFrame) -> None:
    required = {"week_start", "city_cases"}
    if not required.issubset(df.columns):
        raise ValueError("city_weekly requires week_start, city_cases")
    df = df[["week_start", "city_cases"]].copy()
    _upsert_df(sb, "city_weekly", df, conflict="week_start")


def upsert_barangay_weekly(sb: Client, df: pd.DataFrame) -> None:
    required = {"name", "week_start", "cases"}
    if not required.issubset(df.columns):
        raise ValueError("barangay_weekly requires name, week_start, cases")
    df = df[["name", "week_start", "cases"]].copy()
    _upsert_df(sb, "barangay_weekly", df, conflict="name,week_start")


def upsert_barangay_forecasts(sb: Client,   df: pd.DataFrame) -> None:
    required = {
        "name",
        "week_start",
        "final_forecast",
        "hybrid_forecast",
        "local_forecast",
        "is_future",
    }
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"barangay_forecasts missing required columns: {sorted(missing)}")

    # Only send the table columns
    df = df[
        ["name", "week_start", "final_forecast", "hybrid_forecast", "local_forecast", "is_future"]
    ].copy()

    _upsert_df(sb, "barangay_forecasts", df, conflict="name,week_start")



# ============================================================
# MASTER EXPORT FUNCTION
# ============================================================

def upload_to_supabase(cfg) -> None:
    sb = _load_supabase()
    outdir = cfg.out
    run_id = cfg.run_id
    if not run_id:
        raise RuntimeError("cfg.run_id is missing. run_pipeline must set it (uuid string).")

    run_kind = getattr(cfg, "run_kind", "production")  # or "backtest"


    # ---------------------------------------------------------
    # 1) RUNS (FK requirement for *_forecasts_long)
    # ---------------------------------------------------------
    # Try to infer horizon_weeks from any long file that exists
    horizon_weeks = 0
    future_candidates = [
        outdir / "barangay_forecasts_all_models_future_long.csv",
        outdir / "barangay_forecasts_long_future.csv",
    ]

    for p in future_candidates:
        if p.exists():
            tmp = pd.read_csv(p)
            col = "ds" if "ds" in tmp.columns else "week_start"
            horizon_weeks = int(pd.to_datetime(tmp[col], errors="coerce").dt.date.nunique())
            break


    # For backtest, record the cutoff date; for production, store None
    train_end_value = None
    if run_kind == "backtest":
        train_end_value = getattr(cfg, "backtest_end_date", None)

    runs_df = pd.DataFrame([{
        "run_id": run_id,
        "mode": cfg.incoming_mode,
        "train_end": train_end_value,
        "horizon_weeks": horizon_weeks,
        "data_version": None,
        "code_version": None,
        "run_kind": run_kind,
        "status": "running",
        "started_at": _utc_now_iso(),
        "finished_at": None,
        "error_message": None,
    }])
    upsert_runs(sb, runs_df)

   

    try:

         # ---------------------------------------------------------
        # 2) BARANGAYS FIRST (FK requirement for weekly + forecasts)
        # ---------------------------------------------------------
        weekly_path = outdir / "weekly_cases_all_barangays.csv"
        if not weekly_path.exists():
            raise FileNotFoundError(f"Missing required file: {weekly_path}")

        src_bg = pd.read_csv(weekly_path)["Barangay_key"].drop_duplicates()
        df_barangays = pd.DataFrame(
            {"name": src_bg.apply(normalize_barangay_name), "display_name": src_bg}
        )
        upsert_barangays(sb, df_barangays)


        # ---------------------------------------------------------
        # 3) CITY FORECASTS LONG (test+future combined)
        # ---------------------------------------------------------
        city_long_path = outdir / "city_forecasts_long.csv"
        if city_long_path.exists():
            city_long = pd.read_csv(city_long_path)

            # Ensure correct cols + types
            if "run_id" not in city_long.columns:
                city_long["run_id"] = run_id
            city_long["week_start"] = pd.to_datetime(city_long["week_start"], errors="raise").dt.strftime("%Y-%m-%d")

            upsert_city_forecasts_long(sb, city_long)
        else:
            print("ℹ️ Skipped city_forecasts_long: city_forecasts_long.csv not found.")

        # ---------------------------------------------------------
        # 4) BARANGAY FORECASTS LONG
        # Prefer a combined long file if you have it; else fall back to future-only.
        # ---------------------------------------------------------
        bg_long_path = outdir / "barangay_forecasts_long.csv"
        future_only_path = outdir / "barangay_forecasts_all_models_future_long.csv"

        chosen_bg_path = bg_long_path if bg_long_path.exists() else future_only_path

        if chosen_bg_path.exists():
            bg_long = pd.read_csv(chosen_bg_path)

            # Map pipeline columns → Supabase columns
            if "Barangay_key" in bg_long.columns:
                bg_long = bg_long.rename(columns={"Barangay_key": "name"})
            if "ds" in bg_long.columns:
                bg_long = bg_long.rename(columns={"ds": "week_start"})

            bg_long["run_id"] = run_id
            bg_long["name"] = bg_long["name"].apply(normalize_barangay_name)
            bg_long["week_start"] = pd.to_datetime(bg_long["week_start"], errors="raise").dt.strftime("%Y-%m-%d")

            upsert_barangay_forecasts_long(sb, bg_long)
        else:
            print("ℹ️ Skipped barangay_forecasts_long: no long CSV found.")

        # ---------------------------------------------------------
        # 5) CITY WEEKLY
        # ---------------------------------------------------------
        city_weekly_path = outdir / "city_weekly.csv"
        if city_weekly_path.exists():
            df_city_weekly = pd.read_csv(city_weekly_path).rename(
                columns={"WeekStart": "week_start", "CityCases": "city_cases"}
            )
            df_city_weekly["city_cases"] = pd.to_numeric(df_city_weekly["city_cases"], errors="coerce").fillna(0).astype(int)
            df_city_weekly["week_start"] = pd.to_datetime(df_city_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
            upsert_city_weekly(sb, df_city_weekly)
        else:
            print("ℹ️ Skipped city_weekly: city_weekly.csv not found.")

        # ---------------------------------------------------------
        # 6) BARANGAY WEEKLY
        # ---------------------------------------------------------
        df_bg_weekly = pd.read_csv(weekly_path).rename(
            columns={"Barangay_key": "name", "WeekStart": "week_start", "Cases": "cases"}
        )
        df_bg_weekly["name"] = df_bg_weekly["name"].apply(normalize_barangay_name)
        df_bg_weekly["cases"] = pd.to_numeric(df_bg_weekly["cases"], errors="coerce").fillna(0).astype(int)
        df_bg_weekly["week_start"] = pd.to_datetime(df_bg_weekly["week_start"], errors="raise").dt.strftime("%Y-%m-%d")
        upsert_barangay_weekly(sb, df_bg_weekly)

        # ---------------------------------------------------------
        # 7) OPTIONAL legacy wide export (only if you still need it)
        # ---------------------------------------------------------
        # If you're moving fully to long+views, you can delete this block later.
        try:
            wide_path = outdir / "barangay_forecasts_final.csv"
            preferred_long_path = outdir / "barangay_forecasts_preferred_future_long.csv"

            df_fore = None

            if wide_path.exists():
                tmp = pd.read_csv(wide_path)
                wide_required = {"Barangay_key", "ds", "Final", "Forecast"}
                if wide_required.issubset(tmp.columns):
                    df_fore = tmp.rename(columns={
                        "Barangay_key": "name",
                        "ds": "week_start",
                        "Final": "final_forecast",
                        "Forecast": "hybrid_forecast",
                    })
                    if "local_forecast" not in df_fore.columns:
                        df_fore["local_forecast"] = 0.0

            if df_fore is None and preferred_long_path.exists():
                pref = pd.read_csv(preferred_long_path)
                if "model_name" in pref.columns:
                    pref = pref[pref["model_name"] == "preferred"]
                if "horizon_type" in pref.columns:
                    pref = pref[pref["horizon_type"] == "future"]

                df_fore = pref.rename(columns={
                    "Barangay_key": "name",
                    "ds": "week_start",
                    "yhat": "final_forecast",
                })
                df_fore["hybrid_forecast"] = df_fore["final_forecast"]
                df_fore["local_forecast"] = 0.0

            if df_fore is not None and not df_fore.empty:
                df_fore["name"] = df_fore["name"].apply(normalize_barangay_name)
                df_fore["week_start"] = pd.to_datetime(df_fore["week_start"], errors="raise").dt.strftime("%Y-%m-%d")

                last_observed = df_bg_weekly["week_start"].max()
                df_fore["is_future"] = pd.to_datetime(df_fore["week_start"]) > pd.to_datetime(last_observed)

                df_fore = df_fore.replace([float("inf"), float("-inf")], None).fillna(0)
                df_fore["final_forecast"] = pd.to_numeric(df_fore["final_forecast"], errors="coerce").fillna(0).astype(float)
                df_fore["hybrid_forecast"] = pd.to_numeric(df_fore["hybrid_forecast"], errors="coerce").fillna(0).astype(float)
                df_fore["local_forecast"] = pd.to_numeric(df_fore["local_forecast"], errors="coerce").fillna(0).astype(float)

                upsert_barangay_forecasts(sb, df_fore)
            
                

        except Exception as e:
            print(f"ℹ️ Skipped legacy barangay_forecasts export: {e}")
            
        mark_run(sb, run_id, "succeeded")
        print("✅ Supabase export: COMPLETE")

    except Exception as e:
        mark_run(sb, run_id, "failed", error_message=str(e)[:1000])
        raise

if __name__ == "__main__":
    from denguard.config import DEFAULT_CFG

    upload_to_supabase(DEFAULT_CFG)
