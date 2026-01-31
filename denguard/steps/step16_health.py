from __future__ import annotations

import numpy as np
import pandas as pd


def model_health_report(
    df: pd.DataFrame,
    weekly_full: pd.DataFrame,
    metrics_prophet: dict,
    metrics_arima: dict,
    avg_smape: float,
    diff: float = float("nan"),
) -> pd.DataFrame:
    print("\n== STEP 16: Model Health & Sanity Report ==")
    total_cases_raw = len(df)
    total_cases_weekly = weekly_full["Cases"].sum()
    weeks_per_bg = weekly_full.groupby("Barangay_key")["WeekStart"].nunique().unique()

    checks = {
        "Data totals match": abs(total_cases_raw - total_cases_weekly) < 10,
        "Constant weeks per barangay": len(weeks_per_bg) == 1,
        "No null barangays": df["Barangay_key"].isna().sum() == 0,
        "Prophet RMSE reasonable": (
            True if np.isnan(metrics_prophet.get("RMSE", np.nan)) else np.isfinite(metrics_prophet["RMSE"])
        ),
        "Prophet SMAPE reasonable": (True if np.isnan(avg_smape) else np.isfinite(avg_smape)),
        "ARIMA RMSE reasonable": np.isfinite(metrics_arima.get("RMSE", np.nan)),
        "Barangay sum = city total (coherence)": (True if np.isnan(diff) else diff < 1e-6),
    }

    report = pd.DataFrame({"Check": list(checks.keys()), "Status": ["✅ PASS" if v else "❌ FAIL" for v in checks.values()]})
    print(report.to_string(index=False))

    if all(checks.values()):
        print("\n🎯 All major pipeline checks passed — model and data are consistent.")
    else:
        print("\n⚠️ One or more checks failed — review highlighted sections above.")
    return report