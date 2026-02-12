from __future__ import annotations
import pandas as pd
import numpy as np
from denguard.config import Config

def local_eligibility(
    weekly_full: pd.DataFrame,
    cfg: Config,
    *,
    train_end: pd.Timestamp,
) -> tuple[pd.DataFrame, list[str]]:
    df = weekly_full.copy()
    df["WeekStart"] = pd.to_datetime(df["WeekStart"], errors="coerce")
    df = df.dropna(subset=["WeekStart"])
    df = df[df["WeekStart"] <= train_end].copy()

    agg = (df.groupby("Barangay_key", as_index=False)
             .agg(train_weeks=("WeekStart","nunique"),
                  nonzero_weeks=("Cases", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) > 0).sum())),
                  total_cases=("Cases", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0).sum()))
             ))

    min_weeks = int(getattr(cfg, "local_min_train_weeks", 104))
    min_nonzero = int(getattr(cfg, "local_min_nonzero_weeks", 20))
    min_cases = float(getattr(cfg, "local_min_total_cases", 50))

    agg["eligible_local"] = (
        (agg["train_weeks"] >= min_weeks) &
        (agg["nonzero_weeks"] >= min_nonzero) &
        (agg["total_cases"] >= min_cases)
    )

    def _reason(r):
        reasons = []
        if r["train_weeks"] < min_weeks: reasons.append("insufficient_train_weeks")
        if r["nonzero_weeks"] < min_nonzero: reasons.append("too_sparse_nonzero_weeks")
        if r["total_cases"] < min_cases: reasons.append("too_few_total_cases")
        return "ok" if not reasons else "+".join(reasons)

    agg["eligibility_reason"] = agg.apply(_reason, axis=1)

    eligible_keys = agg.loc[agg["eligible_local"], "Barangay_key"].tolist()

    agg["run_id"] = cfg.run_id
    agg.to_csv(cfg.out / "local_eligibility.csv", index=False)

    return agg, eligible_keys
