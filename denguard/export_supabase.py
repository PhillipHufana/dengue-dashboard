# file: denguard/export_supabase.py
from __future__ import annotations

import os
import math
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

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
# PUBLIC UPSERT FUNCTIONS (SAFE: subset to table columns)
# ============================================================

def upsert_barangays(df: pd.DataFrame) -> None:
    required = {"name", "display_name"}
    if not required.issubset(df.columns):
        raise ValueError(f"barangays requires columns: {sorted(required)}")
    # Only send columns that exist in your Supabase table schema
    df = df[["name", "display_name"]].copy()
    _upsert_df("barangays", df, conflict="name")


def upsert_city_weekly(df: pd.DataFrame) -> None:
    required = {"week_start", "city_cases"}
    if not required.issubset(df.columns):
        raise ValueError("city_weekly requires week_start, city_cases")
    df = df[["week_start", "city_cases"]].copy()
    _upsert_df("city_weekly", df, conflict="week_start")


def upsert_barangay_weekly(df: pd.DataFrame) -> None:
    required = {"name", "week_start", "cases"}
    if not required.issubset(df.columns):
        raise ValueError("barangay_weekly requires name, week_start, cases")
    df = df[["name", "week_start", "cases"]].copy()
    _upsert_df("barangay_weekly", df, conflict="name,week_start")


def upsert_barangay_forecasts(df: pd.DataFrame) -> None:
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

    _upsert_df("barangay_forecasts", df, conflict="name,week_start")


# ============================================================
# MASTER EXPORT FUNCTION
# ============================================================

def upload_to_supabase(cfg) -> None:
    outdir = cfg.out

    # ---------------------------------------------------------
    # Barangays (master list)
    # ---------------------------------------------------------
    src_bg = pd.read_csv(outdir / "weekly_cases_all_barangays.csv")[
        "Barangay_key"
    ].drop_duplicates()

    # Normalized name + display_name for UI
    df_barangays = pd.DataFrame(
        {
            "name": src_bg.apply(normalize_barangay_name),
            "display_name": src_bg,
        }
    )

    upsert_barangays(df_barangays)

    # ---------------------------------------------------------
    # City Weekly
    # ---------------------------------------------------------
    df_city_weekly = pd.read_csv(outdir / "city_weekly.csv")

    # Rename first, then enforce integer city_cases
    df_city_weekly = df_city_weekly.rename(
        columns={"WeekStart": "week_start", "CityCases": "city_cases"}
    )

    df_city_weekly["city_cases"] = (
        pd.to_numeric(df_city_weekly["city_cases"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df_city_weekly["week_start"] = (
        pd.to_datetime(df_city_weekly["week_start"])
        .dt.strftime("%Y-%m-%d")
    )

    upsert_city_weekly(df_city_weekly)

    # ---------------------------------------------------------
    # Barangay Weekly
    # ---------------------------------------------------------
    df_bg_weekly = pd.read_csv(outdir / "weekly_cases_all_barangays.csv").rename(
        columns={
            "Barangay_key": "name",
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

    df_bg_weekly["week_start"] = (
        pd.to_datetime(df_bg_weekly["week_start"])
        .dt.strftime("%Y-%m-%d")
    )

    upsert_barangay_weekly(df_bg_weekly)

    # ---------------------------------------------------------
    # Barangay Forecasts (keep existing wide table alive OR fallback to preferred long)
    # ---------------------------------------------------------
    wide_path = outdir / "barangay_forecasts_final.csv"
    preferred_long_path = outdir / "barangay_forecasts_preferred_future_long.csv"

    df_fore = None  # type: ignore

    # 1) Prefer legacy wide file IF it has the expected columns
    if wide_path.exists():
        tmp = pd.read_csv(wide_path)

        wide_required = {"Barangay_key", "ds", "Final", "Forecast"}
        if wide_required.issubset(tmp.columns):
            df_fore = tmp.rename(
                columns={
                    "Barangay_key": "name",
                    "ds": "week_start",
                    "Final": "final_forecast",
                    "Forecast": "hybrid_forecast",
                }
            )
            # local_forecast is optional in old files
            if "local_forecast" not in df_fore.columns:
                df_fore["local_forecast"] = 0.0
        else:
            print("⚠️ barangay_forecasts_final.csv exists but is not in wide schema; falling back to preferred_long.")
            df_fore = None


    # 2) Otherwise fall back to preferred long file and map into wide schema
    if df_fore is None and preferred_long_path.exists():
        pref = pd.read_csv(preferred_long_path)
        if "model_name" in pref.columns:
            pref = pref[pref["model_name"] == "preferred"]
        if "horizon_type" in pref.columns:
            pref = pref[pref["horizon_type"] == "future"]

        df_fore = pref.rename(
            columns={"Barangay_key": "name", "ds": "week_start", "yhat": "final_forecast"}
        )
        df_fore["hybrid_forecast"] = df_fore["final_forecast"]
        df_fore["local_forecast"] = 0.0
        df_fore = df_fore[["name", "week_start", "final_forecast", "hybrid_forecast", "local_forecast"]].copy()

    # 3) No forecasts available
    if df_fore is None:
        print("ℹ️ Skipped barangay_forecasts: no usable forecast CSV found.")
        df_fore = pd.DataFrame(columns=["name", "week_start", "final_forecast", "hybrid_forecast", "local_forecast"])
    
    # ---- SAFETY: guarantee required forecast columns exist even if wide file is partially different ----
    if not df_fore.empty:
        if "week_start" not in df_fore.columns and "ds" in df_fore.columns:
            df_fore = df_fore.rename(columns={"ds": "week_start"})
        if "name" not in df_fore.columns and "Barangay_key" in df_fore.columns:
            df_fore = df_fore.rename(columns={"Barangay_key": "name"})

        # If wide file had different forecast column names, map them
        if "final_forecast" not in df_fore.columns:
            if "Final" in df_fore.columns:
                df_fore["final_forecast"] = df_fore["Final"]
            elif "yhat" in df_fore.columns:
                df_fore["final_forecast"] = df_fore["yhat"]
            else:
                df_fore["final_forecast"] = 0.0

        if "hybrid_forecast" not in df_fore.columns:
            if "Forecast" in df_fore.columns:
                df_fore["hybrid_forecast"] = df_fore["Forecast"]
            else:
                df_fore["hybrid_forecast"] = df_fore["final_forecast"]

        if "local_forecast" not in df_fore.columns:
            df_fore["local_forecast"] = 0.0



    if not df_fore.empty:
        df_fore["name"] = df_fore["name"].apply(normalize_barangay_name)

        df_fore["week_start"] = pd.to_datetime(df_fore["week_start"], errors="coerce").dt.strftime("%Y-%m-%d")
        if df_fore["week_start"].isna().any():
            raise ValueError("Forecast week_start contains invalid dates.")

        # Mark future weeks relative to last observed barangay weekly date
        last_observed = df_bg_weekly["week_start"].max()
        df_fore["is_future"] = (pd.to_datetime(df_fore["week_start"]) > pd.to_datetime(last_observed))

        # Make numeric safe
        df_fore = df_fore.replace([float("inf"), float("-inf")], None).fillna(0)

        df_fore["final_forecast"] = pd.to_numeric(df_fore["final_forecast"], errors="coerce").fillna(0).astype(float)
        df_fore["hybrid_forecast"] = pd.to_numeric(df_fore["hybrid_forecast"], errors="coerce").fillna(0).astype(float)
        df_fore["local_forecast"] = pd.to_numeric(df_fore["local_forecast"], errors="coerce").fillna(0).astype(float)

        upsert_barangay_forecasts(df_fore)


    print("✅ Supabase export: COMPLETE")


if __name__ == "__main__":
    from denguard.config import DEFAULT_CFG

    upload_to_supabase(DEFAULT_CFG)
