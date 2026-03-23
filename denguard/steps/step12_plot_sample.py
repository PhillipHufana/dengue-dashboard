from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt
from denguard.config import Config
from denguard.utils import plot_and_save


def plot_sample_barangays(weekly_full: pd.DataFrame, barangay_forecasts: pd.DataFrame, cfg: Config) -> None:
    """
    Expects barangay_forecasts standardized barangay df:
      Barangay_key, ds, yhat, ..., model_name, horizon_type
    """
    print("\n== STEP 12: Barangay forecast visualization (standardized) ==")

    import seaborn as sns  # keeping to preserve your original behavior

    top_barangays = (
        weekly_full.groupby("Barangay_key")["Cases"].sum()
        .sort_values(ascending=False)
        .head(3)
        .index.tolist()
    )

    sample = barangay_forecasts.query("Barangay_key in @top_barangays").copy()
    if sample.empty:
        raise ValueError("No sample forecasts found for top barangays; check inputs.")

    sample["ds"] = pd.to_datetime(sample["ds"], errors="raise")

    plt.figure(figsize=(12, 5))
    sns.lineplot(data=sample, x="ds", y="yhat", hue="Barangay_key", style="model_name")
    plt.title("Forecasts — Sample Barangays (yhat)")
    plt.xlabel("Week (W-MON)")
    plt.ylabel("Predicted Cases")
    plot_and_save(cfg.out / "barangay_forecast_sample.png")
    print(f" Saved sample forecast plot for top barangays: {top_barangays}")
