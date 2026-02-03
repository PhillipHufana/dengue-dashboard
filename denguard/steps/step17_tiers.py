from __future__ import annotations
from typing import Tuple, List
import pandas as pd
from denguard.config import Config as _Config
import numpy as np

def tier_classification(
    weekly_full: pd.DataFrame,
    cfg: _Config,
    *,
    train_end: pd.Timestamp | None = None,
    K_nonzero_weeks: int = 12,
    C_total_cases: int = 500,
) -> Tuple[pd.DataFrame, List[str], List[str], List[str]]:
    print("\n== STEP 17: Tier Classification ==")

    df = weekly_full.copy()
    required = {"Barangay_key", "WeekStart", "Cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"weekly_full missing required cols: {sorted(missing)}")

    df["WeekStart"] = pd.to_datetime(df["WeekStart"], errors="coerce")
    if df["WeekStart"].isna().any():
        raise ValueError("weekly_full.WeekStart has invalid dates.")

    if train_end is not None:
        df = df[df["WeekStart"] <= pd.to_datetime(train_end)].copy()

    g = df.groupby("Barangay_key")["Cases"]
    stats = pd.DataFrame({
        "Barangay_key": g.sum().index,
        "TotalCases": g.sum().values,
        "NonZeroWeeks": g.apply(lambda s: int((s > 0).sum())).values,
        "Weeks": g.size().values,
    })

    eligible = (stats["NonZeroWeeks"] >= K_nonzero_weeks) & (stats["TotalCases"] >= C_total_cases)
    stats["Tier"] = np.where(eligible, "A", "C")

    tierA = stats.loc[stats["Tier"] == "A", "Barangay_key"].tolist()
    tierB = stats.loc[stats["Tier"] == "B", "Barangay_key"].tolist()  # currently empty unless you define B
    tierC = stats.loc[stats["Tier"] == "C", "Barangay_key"].tolist()

    out = stats.rename(columns={"Barangay_key": "Barangay"})
    out["run_id"] = cfg.run_id  # ✅ add run_id AFTER out exists
    out.to_csv(cfg.out / "barangay_tiers.csv", index=False)

    print(f"Tier A: {len(tierA)}, Tier B: {len(tierB)}, Tier C: {len(tierC)}")
    return out, tierA, tierB, tierC
