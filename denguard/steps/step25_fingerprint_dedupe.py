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

def fingerprint_dedupe(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    df = df.copy()

    required = ["DOnset", "Barangay_key", "DOB", "Sex"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for fingerprint: {missing}")

    df["__donset_norm"] = df["DOnset"].map(_norm_date)
    df["__dob_norm"]    = df["DOB"].map(_norm_date)
    df["__sex_norm"]    = df["Sex"].map(_norm_str)
    df["__bgy_norm"]    = df["Barangay_key"].map(_norm_str)

    complete = (
        (df["__donset_norm"] != "") &
        (df["__dob_norm"]    != "") &
        (df["__sex_norm"]    != "") &
        (df["__bgy_norm"]    != "")
    )
    df["__fp_complete"] = complete

    fp_raw = (
        df.loc[complete, "__donset_norm"] + "|" +
        df.loc[complete, "__bgy_norm"]    + "|" +
        df.loc[complete, "__dob_norm"]    + "|" +
        df.loc[complete, "__sex_norm"]
    )

    df["__fingerprint"] = pd.NA
    df.loc[complete, "__fingerprint"] = fp_raw.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest())

    # audits
    df.loc[~complete].to_csv(cfg.out / "rows_incomplete_fingerprint.csv", index=False)

    # sort so keep='last' means newest upload
    sort_cols = [c for c in ["__fingerprint", "__file_mtime_utc", "__source_file", "__source_row"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, kind="mergesort")

    # fingerprint-level collision audit (candidate collisions)
    dup_mask = df["__fp_complete"] & df["__fingerprint"].duplicated(keep=False)
    if dup_mask.any():
        df.loc[dup_mask].to_csv(cfg.out / "fingerprint_duplicates_audit.csv", index=False)

    vc = df.loc[df["__fp_complete"], "__fingerprint"].value_counts()
    print("Fingerprint groups with >1 row (candidate collisions):", int((vc > 1).sum()))
    print("Max rows in one fingerprint group:", int(vc.max()) if not vc.empty else 0)

    # diagnostics (run regardless)
    if "DOB" in df.columns:
        df["DOB"].value_counts().head(50).to_csv(cfg.out / "top_dobs.csv")
    if "Barangay_key" in df.columns and "DOnset" in df.columns:
        df.groupby(["Barangay_key", "DOnset"]).size().sort_values(ascending=False).head(200)\
          .to_csv(cfg.out / "top_bgy_onset_counts.csv")

    # safer dedupe
    cand = df.loc[df["__fp_complete"]].copy()
    extra_cols = [c for c in ["District", "MW", "DAdmit", "Admitted", "Case Classification"] if c in cand.columns]

    for c in extra_cols:
        cand[c] = cand[c].astype("string").fillna("").str.strip().str.lower()

    if not extra_cols:
        print("⚠️ No extra discriminator columns available; skipping dedupe.")
        out = df.copy()
    else:
        cand["__fp2"] = (
            cand["__fingerprint"].astype("string") + "|" +
            cand[extra_cols].astype("string").agg("|".join, axis=1)
        )

        dup2 = cand["__fp2"].duplicated(keep=False)
        if dup2.any():
            cand.loc[dup2].to_csv(cfg.out / "fingerprint_fp2_duplicates.csv", index=False)

        before = len(cand)
        cand_dedup = cand.drop_duplicates(subset=["__fp2"], keep="last")
        print("Safer fingerprint dedupe dropped:", before - len(cand_dedup))

        out = pd.concat(
            [cand_dedup.drop(columns=["__fp2"]), df.loc[~df["__fp_complete"]]],
            ignore_index=True
        )

    return out
