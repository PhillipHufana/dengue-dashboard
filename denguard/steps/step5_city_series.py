from __future__ import annotations
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save

def build_city_series(weekly_full: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    print("\n== STEP 5: City-wide series for modeling ==")
    city_weekly = (
        weekly_full.groupby("WeekStart")["Cases"]
        .sum()
        .reset_index()
        .rename(columns={"Cases": "CityCases"})
    ).sort_values("WeekStart")

    city_weekly.to_csv(cfg.out / "city_weekly.csv", index=False)
    print("✅ Saved citywide weekly totals")

    plt.figure(figsize=(10, 4))
    plt.plot(city_weekly["WeekStart"], city_weekly["CityCases"])
    plt.title("Citywide Weekly Dengue Cases")
    plot_and_save(cfg.out / "city_weekly_trend.png")
    return city_weekly