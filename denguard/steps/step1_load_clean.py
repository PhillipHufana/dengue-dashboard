from __future__ import annotations

import os
import unicodedata
from typing import Tuple, Dict, List, Optional
import pandas as pd

from denguard.config import Config
from denguard.io_loader import load_new_raw_files

def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("== STEP 1: Load & basic cleaning ==")
    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(cfg.master_data_csv)
        print(f"✅ Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("⚠️ No master dataset yet. Creating a new one.")

    df_new = load_new_raw_files(cfg.incoming_folder)

    if df_new.empty and df_master.empty:
        df_new = pd.read_excel(cfg.raw_xlsx)
        print("✅ Using original RAW file as initial dataset")

    df = pd.concat([df_master, df_new], ignore_index=True).drop_duplicates()
    print(f"✅ Loaded {len(df):,} total rows (master + incoming)")
    print(f"✅ Loaded {len(df):,} rows")
    print("Columns loaded:", df.columns.tolist())

    if "(Current Address) Barangay" not in df.columns:
        raise KeyError("❌ Column '(Current Address) Barangay' not found in raw data.")
    print("Missing Barangay (raw):", df["(Current Address) Barangay"].isna().sum())

    df["Barangay_clean"] = (
        df["(Current Address) Barangay"]
        .astype(str)
        .str.strip()
        .str.lower()
        .apply(lambda x: unicodedata.normalize("NFKC", x))
    )
    df["Barangay_clean"] = df["Barangay_clean"].str.replace(r"\s*\(.*\)", "", regex=True)
    df["Barangay_clean"] = df["Barangay_clean"].str.replace(r"\s+", " ", regex=True)
    print("✅ Barangay column normalized")
    return df, df_master

def persist_clean(df: pd.DataFrame, cfg: Config) -> None:
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Cleaned data saved to {cfg.out / 'dengue_cleaned.csv'}")
    df.to_csv(cfg.master_data_csv, index=False, encoding="utf-8-sig")
    print(f"✅ Master dataset updated → {cfg.master_data_csv}")