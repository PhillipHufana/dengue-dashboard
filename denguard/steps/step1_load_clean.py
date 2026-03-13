from __future__ import annotations

import os
import re
from typing import Any, Tuple

import pandas as pd

from denguard.config import Config
from denguard.io_loader import finalize_processed_registry, load_new_raw_files

MIN_REASONABLE_ONSET = pd.Timestamp("2016-01-01")


def _append_cleaning_step(rows: list[dict[str, Any]], step: str, before: int, after: int) -> None:
    rows.append(
        {
            "step": step,
            "rows_before": int(before),
            "rows_after": int(after),
            "rows_dropped": int(before - after),
            "drop_pct": (float(before - after) / float(before)) if before else 0.0,
        }
    )


def _write_anomaly(df: pd.DataFrame, cfg: Config, anomaly_type: str, frames: list[pd.DataFrame]) -> None:
    if df.empty:
        return
    out = df.copy()
    out["anomaly_type"] = anomaly_type
    frames.append(out)


def _write_case_id_conflicts(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    if "CASE ID" not in df.columns:
        out = pd.DataFrame(columns=["CASE ID", "n_rows", "n_unique_DOnset", "n_unique_DOB", "n_unique_Sex", "n_unique_barangay"])
        out.to_csv(cfg.out / "case_id_conflicts.csv", index=False)
        return out

    base = df.copy()
    base["CASE ID"] = base["CASE ID"].astype("string").str.strip()
    base = base[base["CASE ID"].notna() & (base["CASE ID"] != "")]
    if base.empty:
        out = pd.DataFrame(columns=["CASE ID", "n_rows", "n_unique_DOnset", "n_unique_DOB", "n_unique_Sex", "n_unique_barangay"])
        out.to_csv(cfg.out / "case_id_conflicts.csv", index=False)
        return out

    grouped = (
        base.groupby("CASE ID", dropna=False)
        .agg(
            n_rows=("CASE ID", "size"),
            n_unique_DOnset=("DOnset", lambda s: int(pd.Series(s).astype("string").dropna().nunique())),
            n_unique_DOB=("DOB", lambda s: int(pd.Series(s).astype("string").dropna().nunique())),
            n_unique_Sex=("Sex", lambda s: int(pd.Series(s).astype("string").str.strip().str.lower().dropna().nunique())),
            n_unique_barangay=("Barangay_clean", lambda s: int(pd.Series(s).astype("string").str.strip().str.lower().dropna().nunique())),
        )
        .reset_index()
    )
    conflicts = grouped[
        (grouped["n_rows"] > 1)
        & (
            (grouped["n_unique_DOnset"] > 1)
            | (grouped["n_unique_DOB"] > 1)
            | (grouped["n_unique_Sex"] > 1)
            | (grouped["n_unique_barangay"] > 1)
        )
    ].copy()
    conflicts.to_csv(cfg.out / "case_id_conflicts.csv", index=False)
    return conflicts


def _write_missingness_report(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    cols = [c for c in ["DOnset", "(Current Address) Barangay", "DOB", "Sex", "Age"] if c in df.columns]
    rows = []
    for c in cols:
        ser = df[c]
        rows.append(
            {
                "column_name": c,
                "row_count": int(len(df)),
                "missing_count": int(ser.isna().sum()),
                "missing_pct": float(ser.isna().mean()) if len(df) else 0.0,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(cfg.out / "missingness_report.csv", index=False)
    return out


def _canon_col(s: str) -> str:
    s = (s or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _pick_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    canon_to_orig = {_canon_col(c): c for c in df.columns}
    for a in aliases:
        key = _canon_col(a)
        if key in canon_to_orig:
            return canon_to_orig[key]
    return None


def _standardize_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renames variant columns to canonical column names expected by the rest of pipeline.
    """
    case_id = _pick_col(df, ["CASE ID", "Case ID", "case_id", "caseid", "case number", "caseno", "id"])
    donset = _pick_col(df, ["DOnset", "Donset", "Date Onset", "Date of Onset", "OnsetDate", "date_onset"])
    dob = _pick_col(df, ["DOB", "Dob", "Date of Birth", "Birthdate", "birth_date", "date_of_birth"])
    sex = _pick_col(df, ["Sex", "sex", "Gender", "gender", "M/F", "MF"])
    bgy = _pick_col(
        df,
        ["(Current Address) Barangay", "Barangay", "Current Address Barangay", "Address Barangay", "Brgy", "Brgy."],
    )

    rename_map = {}
    if case_id and case_id != "CASE ID":
        rename_map[case_id] = "CASE ID"
    if donset and donset != "DOnset":
        rename_map[donset] = "DOnset"
    if dob and dob != "DOB":
        rename_map[dob] = "DOB"
    if sex and sex != "Sex":
        rename_map[sex] = "Sex"
    if bgy and bgy != "(Current Address) Barangay":
        rename_map[bgy] = "(Current Address) Barangay"

    if rename_map:
        df = df.rename(columns=rename_map)

    missing = []
    for req in ["CASE ID", "DOnset", "(Current Address) Barangay"]:
        if req not in df.columns:
            missing.append(req)

    if missing:
        raise KeyError(
            f"Missing required columns after standardization: {missing}. "
            f"Found: {list(df.columns)}"
        )

    if "DOB" not in df.columns:
        df["DOB"] = pd.NA
    if "Sex" not in df.columns:
        df["Sex"] = pd.NA

    return df


def load_and_clean(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    print("== STEP 1: Load & basic cleaning ==")
    cleaning_steps: list[dict[str, Any]] = []
    anomaly_frames: list[pd.DataFrame] = []

    if os.path.exists(cfg.master_data_csv):
        df_master = pd.read_csv(cfg.master_data_csv, dtype={"CASE ID": "string"}, low_memory=False)
        print(f" Master dataset loaded ({len(df_master):,} rows)")
    else:
        df_master = pd.DataFrame()
        print("Creating new master dataset")

    print("incoming_folder:", cfg.incoming_folder)
    print("processed_registry_csv:", str(cfg.out / "processed_files.csv"))
    print("out_dir resolved:", str(cfg.out))

    df_new, loaded_files, pending_registry_rows = load_new_raw_files(
        cfg.incoming_folder,
        processed_registry_csv=str(cfg.out / "processed_files.csv"),
    )

    if df_master.empty and df_new.empty:
        raw_path = str(cfg.raw_xlsx)
        if raw_path.lower().endswith(".csv"):
            df_new = pd.read_csv(raw_path, dtype={"CASE ID": "string"}, low_memory=False)
        else:
            df_new = pd.read_excel(raw_path, dtype={"CASE ID": "string"})
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
    else:
        df = pd.concat([df_master, df_new], ignore_index=True)

    print("Rows after merge strategy:", len(df))
    _append_cleaning_step(cleaning_steps, "merge_strategy", len(df), len(df))

    df = _standardize_required_columns(df)

    if "__batch" not in df.columns:
        df["__batch"] = pd.NA

    for c in ["__source_file", "__source_row", "__file_md5"]:
        if c not in df.columns:
            df[c] = pd.NA

    if "__file_mtime_utc" not in df.columns:
        df["__file_mtime_utc"] = pd.NaT
    df["__file_mtime_utc"] = pd.to_datetime(df["__file_mtime_utc"], utc=True, errors="coerce")
    df.loc[df["__file_mtime_utc"].isna(), "__file_mtime_utc"] = pd.Timestamp("1970-01-01", tz="UTC")

    if "CASE ID" in df.columns:
        df["CASE ID"] = df["CASE ID"].astype("string").str.strip()
        vc = df["CASE ID"].value_counts(dropna=False)
        print("CASE ID present. non-null unique:", int(df["CASE ID"].nunique(dropna=True)))
        print("CASE ID counts max:", int(vc.max()) if len(vc) else 0)
        vc.head(50).to_csv(cfg.out / "top_repeated_caseids.csv", index=True)
    else:
        print("No CASE ID column found (continuing).")

    if "(Current Address) Barangay" not in df.columns:
        raise KeyError("Missing column '(Current Address) Barangay'")
    if "DOnset" not in df.columns:
        raise KeyError("Missing column 'DOnset'")

    df["Barangay_clean"] = (
        df["(Current Address) Barangay"]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    blank_bgy = df["Barangay_clean"].isna() | (df["Barangay_clean"].str.strip() == "")
    if blank_bgy.any():
        df.loc[blank_bgy].to_csv(cfg.out / "rows_missing_barangay_raw.csv", index=False)
        _write_anomaly(df.loc[blank_bgy], cfg, "blank_barangay", anomaly_frames)
    before = len(df)
    df = df.loc[~blank_bgy].copy()
    _append_cleaning_step(cleaning_steps, "drop_blank_barangay", before, len(df))

    df["DOnset"] = pd.to_datetime(df["DOnset"], errors="coerce")
    bad_onset = df["DOnset"].isna()
    if bad_onset.any():
        df.loc[bad_onset].to_csv(cfg.out / "rows_missing_donset.csv", index=False)
        _write_anomaly(df.loc[bad_onset], cfg, "invalid_donset_parse", anomaly_frames)
    before = len(df)
    df = df.loc[~bad_onset].copy()
    _append_cleaning_step(cleaning_steps, "drop_invalid_donset", before, len(df))

    today = pd.Timestamp.today().normalize()
    onset_future = df["DOnset"] > today
    if onset_future.any():
        _write_anomaly(df.loc[onset_future], cfg, "donset_in_future", anomaly_frames)
    before = len(df)
    df = df.loc[~onset_future].copy()
    _append_cleaning_step(cleaning_steps, "drop_future_donset", before, len(df))

    onset_too_old = df["DOnset"] < MIN_REASONABLE_ONSET
    if onset_too_old.any():
        _write_anomaly(df.loc[onset_too_old], cfg, "donset_too_old", anomaly_frames)
    before = len(df)
    df = df.loc[~onset_too_old].copy()
    _append_cleaning_step(cleaning_steps, "drop_implausibly_old_donset", before, len(df))

    dob_raw = df["DOB"].copy()
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")
    dob_raw_nonblank = pd.Series(dob_raw, dtype="string").str.strip().fillna("") != ""
    invalid_dob = dob_raw_nonblank & df["DOB"].isna()
    if invalid_dob.any():
        _write_anomaly(df.loc[invalid_dob], cfg, "invalid_dob_parse", anomaly_frames)

    dob_after_onset = df["DOB"].notna() & (df["DOB"] > df["DOnset"])
    if dob_after_onset.any():
        _write_anomaly(df.loc[dob_after_onset], cfg, "dob_after_donset", anomaly_frames)
        df.loc[dob_after_onset, "DOB"] = pd.NaT

    dob_in_future = df["DOB"].notna() & (df["DOB"] > today)
    if dob_in_future.any():
        _write_anomaly(df.loc[dob_in_future], cfg, "dob_in_future", anomaly_frames)
        df.loc[dob_in_future, "DOB"] = pd.NaT

    print("Rows after dropping blank barangay and invalid DOnset:", len(df))

    ignore = {"__file_mtime_utc", "__file_md5", "__source_file", "__source_row", "__batch"}
    cols = [c for c in df.columns if c not in ignore]
    exact_dup_mask = df.duplicated(subset=cols, keep=False)
    print("Rows that are exact duplicates across content:", int(exact_dup_mask.sum()))
    if exact_dup_mask.any():
        df.loc[exact_dup_mask].to_csv(cfg.out / "exact_duplicate_rows.csv", index=False)
        _write_anomaly(df.loc[exact_dup_mask], cfg, "exact_duplicate_content", anomaly_frames)

    _write_case_id_conflicts(df, cfg)
    _write_missingness_report(df, cfg)
    pd.DataFrame(cleaning_steps).to_csv(cfg.out / "cleaning_step_report.csv", index=False)
    if anomaly_frames:
        pd.concat(anomaly_frames, ignore_index=True).to_csv(cfg.out / "date_anomalies.csv", index=False)
    else:
        pd.DataFrame(columns=list(df.columns) + ["anomaly_type"]).to_csv(cfg.out / "date_anomalies.csv", index=False)

    print("Step 1 complete")

    return df, df_master, pending_registry_rows


def persist_clean(df: pd.DataFrame, cfg: Config) -> None:
    df.to_csv(cfg.out / "dengue_cleaned.csv", index=False, encoding="utf-8-sig")
    df.to_csv(cfg.master_data_csv, index=False, encoding="utf-8-sig")
    print("Cleaned dataset saved and master updated")


def finalize_ingestion_registry(cfg: Config, pending_registry_rows: list[dict[str, Any]]) -> None:
    finalize_processed_registry(
        processed_registry_csv=str(cfg.out / "processed_files.csv"),
        pending_rows=pending_registry_rows,
    )
    if pending_registry_rows:
        print(f"Finalized processed file registry ({len(pending_registry_rows)} file(s))")
