from __future__ import annotations
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save

def build_city_series(weekly_full: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    print("\n== STEP 5: City-wide series for modeling ==")

    city_weekly = (
        weekly_full.groupby("WeekStart")["Cases"].sum().reset_index()
        .rename(columns={"Cases": "CityCases"})
    )

    #  G0.4: tag every row with run_id
    city_weekly["run_id"] = cfg.run_id

    city_weekly["WeekStart"] = pd.to_datetime(city_weekly["WeekStart"], errors="raise")
    city_weekly = city_weekly.sort_values("WeekStart")

    city_weekly = city_weekly[["run_id", "WeekStart", "CityCases"]]

    city_weekly.to_csv(cfg.out / "city_weekly.csv", index=False)
    print(" Saved citywide weekly totals")

    plt.figure(figsize=(10, 4))
    plt.plot(city_weekly["WeekStart"], city_weekly["CityCases"])
    plt.title("Citywide Weekly Dengue Cases")
    plot_and_save(cfg.out / "city_weekly_trend.png")

    ws = city_weekly["WeekStart"].sort_values()
    print("city_weekly rows:", len(city_weekly))
    print("CityCases min/mean/max:", city_weekly["CityCases"].min(), city_weekly["CityCases"].mean(), city_weekly["CityCases"].max())
    print("WeekStart range:", ws.min(), "->", ws.max())
    print("WeekStart dayofweek unique:", ws.dt.dayofweek.unique())
    print("Any duplicate weeks?:", ws.duplicated().any())
    print("All 7-day steps?:", ws.diff().dropna().eq(pd.Timedelta(days=7)).all())

    # city total should equal sum of weekly_full cases
    total_city = int(city_weekly["CityCases"].sum())
    total_weekly_full = int(weekly_full["Cases"].sum())
    print("Total CityCases sum:", total_city)
    print("Total weekly_full Cases sum:", total_weekly_full)
    assert total_city == total_weekly_full, "City total != weekly_full total"

    return city_weekly
