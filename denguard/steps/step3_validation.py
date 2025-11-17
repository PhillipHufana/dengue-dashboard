from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save

def validation_summary(df: pd.DataFrame, cfg: Config) -> None:
    print("\n== STEP 3: Validation summary ==")
    print("Unique barangays (raw):", df["(Current Address) Barangay"].nunique())
    print("Unique barangays (standardized):", df["Barangay_standardized"].nunique())
    print("Null barangay count:", df["Barangay_standardized"].isna().sum())

    barangay_counts = (
        df["Barangay_standardized"]
        .value_counts()
        .reset_index()
        .rename(columns={"index": "Barangay_standardized", "Barangay_standardized": "CaseCount"})
    )
    barangay_counts.columns = ["Barangay_standardized", "CaseCount"]
    barangay_counts.to_csv(cfg.out / "barangay_case_counts.csv", index=False)

    plt.figure(figsize=(10, 4))
    barangay_counts.head(20).plot(kind="bar", x="Barangay_standardized", y="CaseCount", legend=False)
    plt.title("Top 20 Barangays by Record Count")
    plt.xticks(rotation=75, ha="right")
    plot_and_save(cfg.out / "barangay_top20.png")
    print("✅ Saved top-20 plot and case counts")

    canonical = pd.read_csv(cfg.canon_csv)
    canonical_set = set(canonical["canonical_name"].str.lower().str.strip())
    data_set = set(df["Barangay_standardized"].str.strip())
    unmatched = [b for b in data_set if b not in canonical_set]
    print(f"🔍 Barangays not in canonical list: {len(unmatched)}")
    if unmatched:
        pd.Series(unmatched, name="unmatched_barangays").to_csv(
            cfg.out / "unmatched_barangays.csv", index=False
        )
        print("📁 Saved unmatched barangays to intermediate/unmatched_barangays.csv")
