# denguard/dashboard/export.py
from __future__ import annotations
import pandas as pd
from denguard.config import DEFAULT_CFG

def build_dashboard_export(cfg=DEFAULT_CFG):
    print("\n== DASHBOARD EXPORT ==")

    final_forecast = pd.read_csv(cfg.out / "barangay_forecasts_final.csv")
    tiers_df = pd.read_csv(cfg.out / "barangay_tiers.csv")

    # Load the undecorated city forecast if needed
    try:
        city_forecast = pd.read_csv(cfg.out / "city_vs_sum_check.csv")[["ds", "CityForecast"]]
    except:
        print("⚠️ Could not load city_vs_sum_check.csv — ensure pipeline ran fully.")
        city_forecast = pd.DataFrame()

    dash = final_forecast.merge(
        tiers_df,
        left_on="Barangay_standardized",
        right_on="Barangay",
        how="left"
    )

    dash = dash.merge(city_forecast, on="ds", how="left")

    dash = dash.rename(columns={
        "Barangay_standardized": "Barangay",
        "Final": "FinalForecast",
        "Forecast": "HybridForecast",
        "local_forecast": "LocalForecast"
    })

    dash = dash[[
        "ds",
        "Barangay",
        "Tier",
        "FinalForecast",
        "LocalForecast",
        "HybridForecast",
        "CityForecast"
    ]]

    out = cfg.out / "dashboard_forecast.csv"
    dash.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"🚀 Exported {out}")

if __name__ == "__main__":
    build_dashboard_export()
