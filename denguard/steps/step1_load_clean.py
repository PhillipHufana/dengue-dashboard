from __future__ import annotations

import os
import pandas as pd
from typing import Tuple
from denguard.config import Config
from denguard.io_loader import load_new_raw_files

def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("== STEP 1: Load & basic cleaning ==")

    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(cfg.master_data_csv, dtype={"CASE ID": "string"}, low_memory=False)
        print(f"✓ Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("Creating new master dataset")

    print("incoming_folder:", cfg.incoming_folder)
    print("processed_registry_csv:", str(cfg.out / "processed_files.csv"))
    print("out_dir resolved:", str(cfg.out))

    df_new = load_new_raw_files(
        cfg.incoming_folder,
        processed_registry_csv=str(cfg.out / "processed_files.csv"),
    )

    if df_new.empty and df_master.empty:
        df_new = pd.read_excel(cfg.raw_xlsx, dtype={"CASE ID": "string"})
        print("Using initial RAW dataset")

    df = pd.concat([df_master, df_new], ignore_index=True)
    print("Rows after concat:", len(df))

    # --- mtime normalization (needed for later 'keep newest' logic) ---
    if "__file_mtime_utc" not in df.columns:
        df["__file_mtime_utc"] = pd.NaT
    df["__file_mtime_utc"] = pd.to_datetime(df["__file_mtime_utc"], utc=True, errors="coerce")
    df.loc[df["__file_mtime_utc"].isna(), "__file_mtime_utc"] = pd.Timestamp("1970-01-01", tz="UTC")

    # --- keep CASE ID only as a diagnostic (do not filter/dedupe on it) ---
    if "CASE ID" in df.columns:
        df["CASE ID"] = df["CASE ID"].astype("string").str.strip()
        vc = df["CASE ID"].value_counts(dropna=False)
        print("CASE ID present. non-null unique:", int(df["CASE ID"].nunique(dropna=True)))
        print("CASE ID counts max:", int(vc.max()) if len(vc) else 0)
        vc.head(50).to_csv(cfg.out / "top_repeated_caseids.csv", index=True)
    else:
        print("⚠️ No CASE ID column found (continuing; fingerprint dedupe will handle uniqueness).")

    # --- required downstream columns ---
    if "(Current Address) Barangay" not in df.columns:
        raise KeyError("Missing column '(Current Address) Barangay'")
    if "DOnset" not in df.columns:
        raise KeyError("Missing column 'DOnset' (needed for weekly aggregation / fingerprint)")

    # --- Barangay_clean (non-destructive) ---
    df["Barangay_clean"] = (
        df["(Current Address) Barangay"]
        .astype("string")              # IMPORTANT: don't turn NaN into "nan"
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    # --- early drop of unusable rows (you said these are basically ~1 each) ---
    # drop blank barangay_clean
    blank_bgy = df["Barangay_clean"].isna() | (df["Barangay_clean"].str.strip() == "")
    if blank_bgy.any():
        df.loc[blank_bgy].to_csv(cfg.out / "rows_missing_barangay_raw.csv", index=False)
    df = df.loc[~blank_bgy].copy()

    # drop invalid/missing DOnset (weekly_aggregation + fingerprint need it)
    df["DOnset"] = pd.to_datetime(df["DOnset"], errors="coerce")
    bad_onset = df["DOnset"].isna()
    if bad_onset.any():
        df.loc[bad_onset].to_csv(cfg.out / "rows_missing_donset.csv", index=False)
    df = df.loc[~bad_onset].copy()

    print("Rows after dropping blank barangay and invalid DOnset:", len(df))

    # --- exact duplicate detection (optional diagnostic) ---
    ignore = {"__file_mtime_utc", "__file_md5", "__source_file"}
    cols = [c for c in df.columns if c not in ignore]
    exact_dup_mask = df.duplicated(subset=cols, keep=False)
    print("Rows that are exact duplicates across content:", int(exact_dup_mask.sum()))
    if exact_dup_mask.any():
        df.loc[exact_dup_mask].to_csv(cfg.out / "exact_duplicate_rows.csv", index=False)


    print("✓ Step 1 complete (no CASE ID dedupe; fingerprint dedupe happens later)")
    return df, df_master

def persist_clean(df: pd.DataFrame, cfg: Config) -> None:
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False, encoding="utf-8-sig")
    df.to_csv(cfg.master_data_csv, index=False, encoding="utf-8-sig")
    print("✓ Cleaned dataset saved and master updated")
