from __future__ import annotations
import hashlib
import pandas as pd
from denguard.config import Config

def _norm_str(x) -> str:
    if x is None or pd.isna(x):
        return ""
    return str(x).strip().lower()

def _norm_date(x) -> str:
    if x is None or pd.isna(x):
        return ""
    dt = pd.to_datetime(x, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d")

def compute_fingerprint(df: pd.DataFrame) -> pd.Series:
    # Requires: DOnset, Barangay_key, DOB, Sex
    don = df["DOnset"].map(_norm_date)
    dob = df["DOB"].map(_norm_date)
    sex = df["Sex"].map(_norm_str)
    bgy = df["Barangay_key"].map(_norm_str)

    complete = (don != "") & (dob != "") & (sex != "") & (bgy != "")
    fp_raw = don.where(complete, "") + "|" + bgy.where(complete, "") + "|" + dob.where(complete, "") + "|" + sex.where(complete, "")
    fp = fp_raw.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest() if s else "")
    return fp

def incremental_filter(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Keep all master rows, but only incoming rows whose fingerprint is not already in master.
    Must run AFTER standardize_barangays (needs Barangay_key).
    """
    if "__batch" not in df.columns:
        raise KeyError("Missing __batch. Add it in Step 1.")

    master = df[df["__batch"] == "master"].copy()
    incoming = df[df["__batch"] == "incoming"].copy()

    # If no master or no incoming, nothing to filter
    if master.empty or incoming.empty:
        return df

    required = ["DOnset", "Barangay_key", "DOB", "Sex"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for incremental filter: {missing}")

    master_fp = compute_fingerprint(master)
    incoming_fp = compute_fingerprint(incoming)

    master_fp_set = set(master_fp[master_fp != ""].unique())
    incoming["__fingerprint"] = incoming_fp.replace("", pd.NA)

    incoming_incomplete = incoming[incoming["__fingerprint"].isna()].copy()
    if not incoming_incomplete.empty:
        incoming_incomplete.to_csv(cfg.out / "incoming_incomplete_fingerprint_kept.csv", index=False)


    # Keep only incoming rows whose fingerprint is NOT in master
    keep_new = incoming["__fingerprint"].isna() | (~incoming["__fingerprint"].isin(master_fp_set))

    dropped = incoming.loc[~keep_new].copy()
    if not dropped.empty:
        dropped.to_csv(cfg.out / "incoming_dropped_already_in_master.csv", index=False)

    incoming_new = incoming.loc[keep_new].copy()

    out = pd.concat([master, incoming_new], ignore_index=True)

    print("Incremental filter: incoming rows:", len(incoming))
    print("Incremental filter: dropped (already in master):", len(dropped))
    print("Incremental filter: kept incoming (new or incomplete):", len(incoming_new))
    print("Incremental filter: output rows:", len(out))

    return out
