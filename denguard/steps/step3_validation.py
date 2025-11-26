from __future__ import annotations
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save

def validation_summary(df: pd.DataFrame, cfg: Config) -> None:
    print("\n== STEP 3: Validation summary ==")

    print("Unique raw:", df["(Current Address) Barangay"].nunique())
    print("Unique standardized:", df["Barangay_standardized"].nunique())
    print("Nulls:", df["Barangay_standardized"].isna().sum())

    counts = (
        df["Barangay_standardized"]
        .value_counts()
        .rename_axis("Barangay_standardized")
        .reset_index(name="CaseCount")
    )
    counts.to_csv(cfg.out / "barangay_case_counts.csv", index=False)

    plt.figure(figsize=(10, 4))
    counts.head(20).plot(kind="bar", x="Barangay_standardized", y="CaseCount", legend=False)
    plt.xticks(rotation=75)
    plot_and_save(cfg.out / "barangay_top20.png")

    # Compare with canonical
    canonical = pd.read_csv(cfg.canon_csv)
    canonical_set = set(canonical["canonical_name"].str.lower().str.strip())

    data_set = set(df["Barangay_standardized"].str.strip())

    unmatched = sorted([b for b in data_set if b not in canonical_set])

    print("Unmatched:", len(unmatched))
    if unmatched:
        pd.Series(unmatched).to_csv(cfg.out / "unmatched_barangays.csv", index=False)
        print("Saved unmatched list")
