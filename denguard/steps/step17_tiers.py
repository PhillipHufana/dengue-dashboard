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
    C_total_cases: int = 50,
) -> Tuple[pd.DataFrame, List[str], List[str], List[str]]:
    print("\n== STEP 17: Tier Classification ==")

    df = weekly_full.copy()
    df["WeekStart"] = pd.to_datetime(df["WeekStart"], errors="coerce")
    if df["WeekStart"].isna().any():
        raise ValueError("weekly_full.WeekStart has invalid dates.")

    # ✅ Align tiering with training window (backtest consistency)
    if train_end is not None:
        df = df[df["WeekStart"] <= pd.to_datetime(train_end)].copy()

    # Safeguard: required cols
    required = {"Barangay_key", "WeekStart", "Cases"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"weekly_full missing required cols: {sorted(missing)}")

    # Compute sufficiency stats
    g = df.groupby("Barangay_key")["Cases"]
    stats = pd.DataFrame({
        "Barangay_key": g.sum().index,
        "TotalCases": g.sum().values,
        "NonZeroWeeks": g.apply(lambda s: int((s > 0).sum())).values,
        "Weeks": g.size().values,
    })

    # Tier rules
    eligible = (stats["NonZeroWeeks"] >= K_nonzero_weeks) & (stats["TotalCases"] >= C_total_cases)

    # Simple 3-tier split:
    # A = eligible (run local models + compare)
    # C = not eligible (use disagg as preferred)
    # B = optional middle bucket if you want it later (here: keep empty or define your own)
    stats["Tier"] = np.where(eligible, "A", "C")

    tierA = stats.loc[stats["Tier"] == "A", "Barangay_key"].tolist()
    tierB = stats.loc[stats["Tier"] == "B", "Barangay_key"].tolist()
    tierC = stats.loc[stats["Tier"] == "C", "Barangay_key"].tolist()

    # Save
    out = stats.rename(columns={"Barangay_key": "Barangay"})
    out.to_csv(cfg.out / "barangay_tiers.csv", index=False)

    print(f"Tier A: {len(tierA)}, Tier B: {len(tierB)}, Tier C: {len(tierC)}")
    return out, tierA, tierB, tierC
