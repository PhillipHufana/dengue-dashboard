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

    print("incoming_folder:", cfg.incoming_folder)
    print("processed_registry_csv:", str(cfg.out / "processed_files.csv"))
    print("out_dir resolved:", str(cfg.out))

    df_new = load_new_raw_files(
        cfg.incoming_folder,
        processed_registry_csv=str(cfg.out / "processed_files.csv")
    )


    if df_new.empty and df_master.empty:
        df_new = pd.read_excel(cfg.raw_xlsx, dtype={"CASE ID": "string"})
        print("Using initial RAW dataset")

    df = pd.concat([df_master, df_new], ignore_index=True)
    rows_after_concat = len(df)
    print("Rows after concat:", rows_after_concat)

    # --- mtime normalization ---
    if "__file_mtime_utc" not in df.columns:
        df["__file_mtime_utc"] = pd.NaT
    df["__file_mtime_utc"] = pd.to_datetime(df["__file_mtime_utc"], utc=True, errors="coerce")
    df.loc[df["__file_mtime_utc"].isna(), "__file_mtime_utc"] = pd.Timestamp("1970-01-01", tz="UTC")

    if "CASE ID" not in df.columns:
        raise KeyError("Missing column 'CASE ID' (required for deduplication)")

    df["CASE ID"] = df["CASE ID"].astype("string").str.strip()

    example_id = vc.index[0]
    df_valid[df_valid["CASE ID"] == example_id].to_csv(cfg.out / "example_caseid_group.csv", index=False)
    print("Example CASE ID:", example_id, "rows:", int(vc.iloc[0]))

    ignore = {"__file_mtime_utc","__file_md5","__source_file"}
    cols = [c for c in df_valid.columns if c not in ignore]
    exact_dup_mask = df_valid.duplicated(subset=cols, keep=False)
    print("Rows that are exact duplicates across content:", int(exact_dup_mask.sum()))
    df_valid.loc[exact_dup_mask].to_csv(cfg.out / "exact_duplicate_rows.csv", index=False)



    # --- bad case ids ---
    bad_caseid = df["CASE ID"].isna() | (df["CASE ID"].str.strip() == "")
    n_bad_caseid = int(bad_caseid.sum())
    if n_bad_caseid:
        df.loc[bad_caseid].to_csv(cfg.out / "rows_missing_caseid.csv", index=False)
    df_valid = df.loc[~bad_caseid].copy()
    print("Rows after removing missing/blank CASE ID:", len(df_valid))
    print("Missing/blank CASE ID rows:", n_bad_caseid)

    vc = df_valid["CASE ID"].value_counts()
    print("CASE ID counts: min/median/mean/max =",
        int(vc.min()), int(vc.median()), float(vc.mean()), int(vc.max()))
    print("CASE IDs with count==2:", int((vc==2).sum()))
    print("CASE IDs with count>=10:", int((vc>=10).sum()))
    vc.head(50).to_csv(cfg.out / "top_repeated_caseids.csv")


    # --- sort so keep='last' means newest ---
    sort_cols = [c for c in ["CASE ID", "__file_mtime_utc", "__source_file"] if c in df_valid.columns]
    if sort_cols:
        df_valid = df_valid.sort_values(sort_cols, kind="mergesort")

    # --- duplicate audit BEFORE dedupe ---
    dup_mask = df_valid["CASE ID"].duplicated(keep=False)
    n_dup_rows = int(dup_mask.sum())
    n_unique_caseids = int(df_valid["CASE ID"].nunique(dropna=True))
    print("Duplicate CASE ID rows (in duplicate groups):", n_dup_rows)
    print("Unique CASE IDs:", n_unique_caseids)

    if n_dup_rows:
        dup_df = df_valid.loc[dup_mask].copy()
        dup_df["__keep_last"] = False
        kept_idx = df_valid.drop_duplicates(subset=["CASE ID"], keep="last").index
        dup_df.loc[dup_df.index.isin(kept_idx), "__keep_last"] = True
        dup_df.to_csv(cfg.out / "caseid_duplicates_audit.csv", index=False)

    # --- compute dropped rows correctly ---
    before_df = df_valid.copy()
    after_df = df_valid.drop_duplicates(subset=["CASE ID"], keep="last")
    dropped = before_df.loc[~before_df.index.isin(after_df.index)].copy()
    if not dropped.empty:
        dropped.to_csv(cfg.out / "caseid_dropped_rows.csv", index=False)

    df = after_df
    print("Rows after dedupe:", len(df))
    print("Dropped rows:", len(before_df) - len(df))

    # Optional: one-line reconciliation summary
    print("Reconciliation:",
        "concat=", rows_after_concat,
        "bad_caseid=", n_bad_caseid,
        "dedup_dropped=", len(before_df) - len(df),
        "final=", len(df))


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
