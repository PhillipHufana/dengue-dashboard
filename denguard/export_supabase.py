from __future__ import annotations

import os
import math
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Correct normalization import
from denguard.normalize import normalize_barangay_name  

load_dotenv()

# ============================================================
# INTERNAL: Create Supabase Client
# ============================================================

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

def _upsert_df(table: str, df: pd.DataFrame, conflict: str, chunk_size: int = 500) -> None:

    if df.empty:
        print(f"ℹ️ Skipped {table}: empty dataframe.")
        return

    sb = _load_supabase()
    records = df.to_dict(orient="records")

    total = len(records)
    batches = math.ceil(total / chunk_size)

    for i in range(batches):
        batch = records[i * chunk_size:(i + 1) * chunk_size]
        try:
            sb.table(table).upsert(batch, on_conflict=conflict).execute()
        except Exception as e:
            print(f"❌ Error during upsert into {table}: {e}")
            raise

    print(f"✅ Upserted {total} rows into {table}")


# ============================================================
# PUBLIC UPSERT FUNCTIONS
# ============================================================

def upsert_barangays(df: pd.DataFrame):
    if not {"name"}.issubset(df.columns):
        raise ValueError("barangays requires column: name")
    _upsert_df("barangays", df, conflict="name")


def upsert_city_weekly(df: pd.DataFrame):
    if not {"week_start", "city_cases"}.issubset(df.columns):
        raise ValueError("city_weekly requires week_start, city_cases")
    _upsert_df("city_weekly", df, conflict="week_start")


def upsert_barangay_weekly(df: pd.DataFrame):
    if not {"name", "week_start", "cases"}.issubset(df.columns):
        raise ValueError("barangay_weekly requires name, week_start, cases")
    _upsert_df("barangay_weekly", df, conflict="name,week_start")


def upsert_barangay_forecasts(df: pd.DataFrame):
    required = {
        "name",
        "week_start",
        "final_forecast",
        "hybrid_forecast",
        "local_forecast",
        "is_future",
    }
    if not required.issubset(df.columns):
        raise ValueError(f"barangay_forecasts missing required columns: {required}")
    _upsert_df("barangay_forecasts", df, conflict="name,week_start")


# ============================================================
# MASTER EXPORT FUNCTION
# ============================================================

def upload_to_supabase(cfg):

    outdir = cfg.out

    # ---------------------------------------------------------
    # Barangays (master list)
    # ---------------------------------------------------------
    df_barangays = (
        pd.read_csv(outdir / "weekly_cases_all_barangays.csv")["Barangay_standardized"]
        .drop_duplicates()
        .to_frame(name="name")
    )

    df_barangays["name"] = df_barangays["name"].apply(normalize_barangay_name)

    upsert_barangays(df_barangays)

    # ---------------------------------------------------------
    # City Weekly  (FIXED ORDER)
    # ---------------------------------------------------------
    df_city_weekly = pd.read_csv(outdir / "city_weekly.csv")

    # Fix numeric BEFORE rename
    df_city_weekly["CityCases"] = (
        pd.to_numeric(df_city_weekly["CityCases"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df_city_weekly = df_city_weekly.rename(
        columns={"WeekStart": "week_start", "CityCases": "city_cases"}
    )

    df_city_weekly["week_start"] = pd.to_datetime(df_city_weekly["week_start"])\
        .dt.strftime("%Y-%m-%d")

    upsert_city_weekly(df_city_weekly)

    # ---------------------------------------------------------
    # Barangay Weekly
    # ---------------------------------------------------------
    df_bg_weekly = pd.read_csv(outdir / "weekly_cases_all_barangays.csv").rename(
        columns={
            "Barangay_standardized": "name",
            "WeekStart": "week_start",
            "Cases": "cases",
        }
    )

    df_bg_weekly["name"] = df_bg_weekly["name"].apply(normalize_barangay_name)

    df_bg_weekly["cases"] = (
        pd.to_numeric(df_bg_weekly["cases"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df_bg_weekly["week_start"] = pd.to_datetime(df_bg_weekly["week_start"])\
        .dt.strftime("%Y-%m-%d")

    upsert_barangay_weekly(df_bg_weekly)

    # ---------------------------------------------------------
    # Barangay Forecasts
    # ---------------------------------------------------------
    df_fore = pd.read_csv(outdir / "barangay_forecasts_final.csv").rename(
        columns={
            "Barangay_standardized": "name",
            "ds": "week_start",
            "Final": "final_forecast",
            "Forecast": "hybrid_forecast",
            "local_forecast": "local_forecast",
        }
    )

    df_fore["name"] = df_fore["name"].apply(normalize_barangay_name)

    df_fore["week_start"] = pd.to_datetime(df_fore["week_start"])\
        .dt.strftime("%Y-%m-%d")

    last_observed = df_bg_weekly["week_start"].max()
    df_fore["is_future"] = pd.to_datetime(df_fore["week_start"]) > pd.to_datetime(last_observed)

    df_fore = df_fore.replace([float("inf"), float("-inf")], None).fillna(0)

    df_fore["final_forecast"] = df_fore["final_forecast"].astype(float)
    df_fore["hybrid_forecast"] = df_fore["hybrid_forecast"].astype(float)
    df_fore["local_forecast"] = df_fore["local_forecast"].astype(float)

    upsert_barangay_forecasts(df_fore)

    print("✅ Supabase export: COMPLETE")

if __name__ == "__main__":
    from denguard.config import DEFAULT_CFG
    upload_to_supabase(DEFAULT_CFG)
