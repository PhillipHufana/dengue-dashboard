from __future__ import annotations

import pandas as pd
from denguard.config import Config

def weekly_aggregation(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    print("\n== STEP 4: Weekly aggregation ==")
    df = df.copy()
    df["date_onset"] = pd.to_datetime(df["DOnset"], errors="coerce")
    df = df.dropna(subset=["date_onset"])
    df = df[df["date_onset"].between("2017-01-01", "2025-12-31")]

    df["WeekStart"] = df["date_onset"] - pd.to_timedelta(df["date_onset"].dt.weekday, unit="d")
    df["WeekStart"] = df["WeekStart"].dt.floor("D")

    weekly = (
        df.groupby(["Barangay_standardized", "WeekStart"])
        .size()
        .reset_index(name="Cases")
    )

    start_date = df["WeekStart"].min().floor("D")
    end_date = weekly["WeekStart"].max()
    weeks = pd.date_range(start_date, end_date, freq="W-MON")
    barangays = weekly["Barangay_standardized"].unique()

    template = pd.MultiIndex.from_product(
        [barangays, weeks], names=["Barangay_standardized", "WeekStart"]
    ).to_frame(index=False)

    weekly_full = (
        template.merge(weekly, on=["Barangay_standardized", "WeekStart"], how="left")
        .fillna({"Cases": 0})
        .sort_values(["Barangay_standardized", "WeekStart"])
    )

    week_counts = weekly_full.groupby("Barangay_standardized")["WeekStart"].count()
    assert week_counts.nunique() == 1, "❌ Inconsistent week counts per barangay!"
    print(f"✅ All barangays have {week_counts.iloc[0]} weeks of data.")
    weekly_full.to_csv(cfg.out / "weekly_cases_all_barangays.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Saved full weekly dataset ({len(weekly_full):,} rows)")
    return weekly_full
