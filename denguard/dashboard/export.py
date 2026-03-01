# denguard/dashboard/export.py
from __future__ import annotations

from denguard.config import DEFAULT_CFG
from denguard.export.dashboard_export import produce_dashboard_forecast


def build_dashboard_export(cfg=DEFAULT_CFG):
    print("\n== DASHBOARD EXPORT ==")
    dash = produce_dashboard_forecast(cfg)
    print(f"Exported {cfg.out / 'dashboard_forecast.csv'}")
    return dash


if __name__ == "__main__":
    build_dashboard_export()
