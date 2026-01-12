from __future__ import annotations

import os
import pandas as pd
from typing import Tuple
from denguard.config import Config
from denguard.io_loader import load_new_raw_files

def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("== STEP 1: Load & basic cleaning ==")

    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(
            cfg.master_data_csv,
            dtype={"CASE ID": "string"},
            low_memory=False
        )
        print(f"✓ Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("Creating new master dataset")

    df_new = load_new_raw_files(
        cfg.incoming_folder,
        processed_registry_csv=str(cfg.out / "processed_files.csv")
    )


    if df_new.empty and df_master.empty:
        df_new = pd.read_excel(cfg.raw_xlsx, dtype={"CASE ID": "string"})
        print("Using initial RAW dataset")

    df = pd.concat([df_master, df_new], ignore_index=True)

    if "CASE ID" not in df.columns:
        raise KeyError("Missing column 'CASE ID' (required for deduplication)")

    # normalize CASE ID
    df["CASE ID"] = df["CASE ID"].astype("string").str.strip()

    # keep the newest copy of the same case if re-uploaded
    sort_cols = [c for c in ["__file_mtime_utc", "__source_file"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols)
    df = df.drop_duplicates(subset=["CASE ID"], keep="last")

    if "(Current Address) Barangay" not in df.columns:
        raise KeyError("Missing column '(Current Address) Barangay'")

    # Clean, but DO NOT remove parentheses, accents or content
    df["Barangay_clean"] = (
        df["(Current Address) Barangay"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)  # collapse spaces
    )

    print("✓ Barangay_clean created (non-destructive)")
    return df, df_master

def persist_clean(df: pd.DataFrame, cfg: Config) -> None:
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False, encoding="utf-8-sig")
    df.to_csv(cfg.master_data_csv, index=False, encoding="utf-8-sig")
    print("✓ Cleaned dataset saved and master updated")
