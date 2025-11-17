from __future__ import annotations
import pandas as pd
import matplotlib.pyplot as plt
from denguard.config import Config
from denguard.utils import plot_and_save

def plot_sample_barangays(weekly_full: pd.DataFrame, barangay_forecasts: pd.DataFrame, cfg: Config) -> None:
    print("\n== STEP 12: Barangay hybrid forecast visualization ==")
    import seaborn as sns  # keep to preserve original behavior

    top_barangays = (
        weekly_full.groupby("Barangay_standardized")["Cases"].sum()
        .sort_values(ascending=False)
        .head(3)
        .index.tolist()
    )

    sample_forecasts = barangay_forecasts.query("Barangay_standardized in @top_barangays")
    plt.figure(figsize=(12, 5))
    sns.lineplot(data=sample_forecasts, x="ds", y="Forecast", hue="Barangay_standardized")
    plt.title("Hybrid Top-Down Forecasts — Sample Barangays")
    plt.xlabel("Week")
    plt.ylabel("Predicted Cases")
    plot_and_save(cfg.out / "barangay_forecast_sample.png")
    print(f"✅ Saved sample forecast plot for top barangays: {top_barangays}")
