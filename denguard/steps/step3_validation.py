from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save
from denguard.keys import make_barangay_db_key

def validation_summary(df: pd.DataFrame, cfg: Config) -> None:
    print("\n== STEP 3: Validation summary ==")

    if "Barangay_key" not in df.columns:
        raise KeyError("Missing 'Barangay_key' (run Step 2 first)")

    print("Unique raw:", df["(Current Address) Barangay"].nunique())
    print("Unique keys:", df["Barangay_key"].nunique(dropna=True))

    null_count = df["Barangay_key"].isna().sum()
    print("Nulls:", null_count)

    if null_count:
        (df.loc[df["Barangay_key"].isna(), "(Current Address) Barangay"]
            .value_counts()
            .rename_axis("raw_barangay")
            .reset_index(name="rows")
            .to_csv(cfg.out / "unmapped_raw_barangays.csv", index=False)
        )
        print("Saved unmapped raw barangays list")

    counts = (
        df["Barangay_key"]
        .value_counts(dropna=True)
        .rename_axis("Barangay_key")
        .reset_index(name="CaseCount")
    )
    counts.to_csv(cfg.out / "barangay_case_counts.csv", index=False)

    plt.figure(figsize=(10, 4))
    counts.head(20).plot(kind="bar", x="Barangay_key", y="CaseCount", legend=False)
    plt.xticks(rotation=75)
    plot_and_save(cfg.out / "barangay_top20.png")

    # Compare with canonical using the same keying function
    canonical = pd.read_csv(cfg.canon_csv)
    canonical_keys = set(canonical["canonical_name"].map(make_barangay_db_key).dropna())

    data_keys = set(df["Barangay_key"].dropna())

    unmatched = sorted(data_keys - canonical_keys)

    print("Unmatched:", len(unmatched))
    if unmatched:
        pd.Series(unmatched, name="Barangay_key").to_csv(cfg.out / "unmatched_barangays.csv", index=False)
        print("Saved unmatched list")

    # How many rows per key (already saved)
    # Additional: how many distinct raw names map to each key (collapse indicator)
    collapse = (
        df.dropna(subset=["Barangay_key"])
        .groupby("Barangay_key")["Barangay_clean"]
        .nunique()
        .sort_values(ascending=False)
        .reset_index(name="n_raw_names")
    )
    collapse.to_csv(cfg.out / "barangay_key_collisions.csv", index=False)
    print("Keys with >1 raw name mapping:", int((collapse["n_raw_names"] > 1).sum()))

