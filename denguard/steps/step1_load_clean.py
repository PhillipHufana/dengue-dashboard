from __future__ import annotations

import os
import pandas as pd
from typing import Tuple
from denguard.config import Config
from denguard.io_loader import load_new_raw_files


def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("== STEP 1: Load & basic cleaning ==")

    # Load master if exists
    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(cfg.master_data_csv, dtype={"CASE ID": "string"}, low_memory=False)
        print(f"✓ Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("Creating new master dataset")

    print("incoming_folder:", cfg.incoming_folder)
    print("processed_registry_csv:", str(cfg.out / "processed_files.csv"))
    print("out_dir resolved:", str(cfg.out))

    df_new, loaded_files = load_new_raw_files(
        cfg.incoming_folder,
        processed_registry_csv=str(cfg.out / "processed_files.csv"),
    )

    # Initial bootstrap: if nothing exists anywhere, load cfg.raw_xlsx once
    if df_master.empty and df_new.empty:
        df_new = pd.read_excel(cfg.raw_xlsx, dtype={"CASE ID": "string"})
        loaded_files = [os.path.basename(cfg.raw_xlsx)]
        print("Using initial RAW dataset")

    if not df_master.empty:
        df_master = df_master.copy()
        df_master["__batch"] = "master"

    if not df_new.empty:
        df_new = df_new.copy()
        df_new["__batch"] = "incoming"




   
    if cfg.incoming_mode == "full_refresh":
        df = df_new.copy() if not df_new.empty else df_master.copy()
    else:  # "incremental"
        df = pd.concat([df_master, df_new], ignore_index=True)


    print("Rows after merge strategy:", len(df))

    if "__batch" not in df.columns:
        df["__batch"] = pd.NA


    # Ensure loader metadata columns exist
    for c in ["__source_file", "__source_row", "__file_md5"]:
        if c not in df.columns:
            df[c] = pd.NA

    if "__file_mtime_utc" not in df.columns:
        df["__file_mtime_utc"] = pd.NaT
    df["__file_mtime_utc"] = pd.to_datetime(df["__file_mtime_utc"], utc=True, errors="coerce")
    df.loc[df["__file_mtime_utc"].isna(), "__file_mtime_utc"] = pd.Timestamp("1970-01-01", tz="UTC")

    # CASE ID diagnostics only
    if "CASE ID" in df.columns:
        df["CASE ID"] = df["CASE ID"].astype("string").str.strip()
        vc = df["CASE ID"].value_counts(dropna=False)
        print("CASE ID present. non-null unique:", int(df["CASE ID"].nunique(dropna=True)))
        print("CASE ID counts max:", int(vc.max()) if len(vc) else 0)
        vc.head(50).to_csv(cfg.out / "top_repeated_caseids.csv", index=True)
    else:
        print("⚠️ No CASE ID column found (continuing).")

    # Required downstream columns
    if "(Current Address) Barangay" not in df.columns:
        raise KeyError("Missing column '(Current Address) Barangay'")
    if "DOnset" not in df.columns:
        raise KeyError("Missing column 'DOnset'")

    # Barangay_clean (keep NA as NA)
    df["Barangay_clean"] = (
        df["(Current Address) Barangay"]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    # Drop blank barangay
    blank_bgy = df["Barangay_clean"].isna() | (df["Barangay_clean"].str.strip() == "")
    if blank_bgy.any():
        df.loc[blank_bgy].to_csv(cfg.out / "rows_missing_barangay_raw.csv", index=False)
    df = df.loc[~blank_bgy].copy()

    # Normalize DOnset to datetime (keep in column; Step 4 uses it)
    df["DOnset"] = pd.to_datetime(df["DOnset"], errors="coerce")
    bad_onset = df["DOnset"].isna()
    if bad_onset.any():
        df.loc[bad_onset].to_csv(cfg.out / "rows_missing_donset.csv", index=False)
    df = df.loc[~bad_onset].copy()

    print("Rows after dropping blank barangay and invalid DOnset:", len(df))

    # Exact duplicate diagnostic (ignore source/meta cols)
    ignore = {"__file_mtime_utc", "__file_md5", "__source_file", "__source_row","__batch"}
    cols = [c for c in df.columns if c not in ignore]
    exact_dup_mask = df.duplicated(subset=cols, keep=False)
    print("Rows that are exact duplicates across content:", int(exact_dup_mask.sum()))
    if exact_dup_mask.any():
        df.loc[exact_dup_mask].to_csv(cfg.out / "exact_duplicate_rows.csv", index=False)

    print("✓ Step 1 complete")



    return df, df_master

def persist_clean(df: pd.DataFrame, cfg: Config) -> None:
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False, encoding="utf-8-sig")
    df.to_csv(cfg.master_data_csv, index=False, encoding="utf-8-sig")
    print("✓ Cleaned dataset saved and master updated")