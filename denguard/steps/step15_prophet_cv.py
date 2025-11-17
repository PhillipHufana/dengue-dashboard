from __future__ import annotations
import matplotlib.pyplot as plt
from denguard.config import Config
from denguard.utils import plot_and_save

def prophet_cross_validation(PROPHET_OK: bool, model_prophet, cfg: Config) -> None:
    if not PROPHET_OK or model_prophet is None:
        print("\n== STEP 15: Prophet cross-validation diagnostics ==")
        print("⚠️ Prophet not available; skipping cross-validation diagnostics.")
        return

    from prophet.diagnostics import cross_validation, performance_metrics

    print("\n== STEP 15: Prophet cross-validation diagnostics ==")
    cv_results = cross_validation(
        model=model_prophet,
        initial="1500 days",
        period="180 days",
        horizon="365 days",
        parallel="processes",
    )
    cv_metrics = performance_metrics(cv_results)
    summary_cols = ["horizon", "rmse", "mae", "mape", "smape"]
    print(cv_metrics[summary_cols].groupby("horizon").mean().tail())
    avg_rmse = cv_metrics["rmse"].mean()
    avg_smape = cv_metrics["smape"].mean()
    print(f"✅ CV average RMSE: {avg_rmse:.2f} | SMAPE: {avg_smape:.3f}")
    plt.figure(figsize=(8, 4))
    plt.plot(cv_metrics["horizon"], cv_metrics["rmse"], "o", alpha=0.5)
    plt.axhline(avg_rmse, color="red", linestyle="--", label=f"Avg RMSE={avg_rmse:.1f}")
    plt.title("Prophet Cross-Validation RMSE over Horizon")
    plt.xlabel("Forecast Horizon")
    plt.ylabel("RMSE")
    plt.legend()
    plot_and_save(cfg.out / "prophet_cv_rmse.png")