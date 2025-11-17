from __future__ import annotations
from typing import Tuple, List
import pandas as pd
from denguard.config import Config as _Config

def tier_classification(weekly_full: pd.DataFrame, cfg: _Config) -> Tuple[pd.DataFrame, List[str], List[str], List[str]]:
    print("\n== STEP 17: Tier Classification ==")
    case_counts = weekly_full.groupby("Barangay_standardized")["Cases"].sum()
    tierA = case_counts[case_counts >= 400].index.tolist()
    tierB = case_counts[(case_counts >= 200) & (case_counts < 400)].index.tolist()
    tierC = case_counts[case_counts < 200].index.tolist()

    tiers_df = pd.DataFrame(
        {
            "Barangay": case_counts.index,
            "TotalCases": case_counts.values,
            "Tier": ["A" if b in tierA else ("B" if b in tierB else "C") for b in case_counts.index],
        }
    )
    tiers_df.to_csv(cfg.out / "barangay_tiers.csv", index=False)
    print(f"Tier A: {len(tierA)}, Tier B: {len(tierB)}, Tier C: {len(tierC)}")
    return tiers_df, tierA, tierB, tierC
