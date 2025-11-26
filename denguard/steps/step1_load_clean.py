from __future__ import annotations

import os
import pandas as pd
from typing import Tuple
from denguard.config import Config
from denguard.io_loader import load_new_raw_files

def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("== STEP 1: Load & basic cleaning ==")

    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(cfg.master_data_csv)
        print(f"✓ Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("Creating new master dataset")

    df_new = load_new_raw_files(cfg.incoming_folder)

    if df_new.empty and df_master.empty:
        df_new = pd.read_excel(cfg.raw_xlsx)
        print("Using initial RAW dataset")

    df = pd.concat([df_master, df_new], ignore_index=True).drop_duplicates()

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
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False)
    df.to_csv(cfg.master_data_csv, index=False)
    print("✓ Cleaned dataset saved and master updated")
