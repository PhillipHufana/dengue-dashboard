from __future__ import annotations
from typing import List, Tuple
import numpy as np
import pandas as pd

from denguard.config import Config

def local_models_tierA(
    tierA: List[str],
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    train_end: pd.Timestamp,
    horizon: int,
    PROPHET_OK: bool,
    cfg: Config,
):
    import pmdarima as pm
    from sklearn.metrics import mean_squared_error

    if horizon <= 0:
        raise ValueError("Horizon must be positive.")

    test_ds = pd.DatetimeIndex(test_city["ds"]).sort_values()
    future_ds = pd.date_range(
        start=test_ds.max() + pd.Timedelta(weeks=1),
        periods=horizon,
        freq="W-MON",
    )

    local_results = []
    all_outputs = []

    for bgy in tierA:
        df_full = (
            weekly_full.loc[
                weekly_full["Barangay_standardized"] == bgy,
                ["WeekStart", "Cases"]
            ]
            .rename(columns={"WeekStart": "ds", "Cases": "y"})
            .copy()
        )

        df_full["ds"] = pd.to_datetime(df_full["ds"])
        df_full["y"] = pd.to_numeric(df_full["y"], errors="coerce").fillna(0.0)

        df_full = (
            df_full.groupby("ds", as_index=False)
            .agg({"y": "sum"})
            .sort_values("ds")
            .reset_index(drop=True)
        )

        if len(df_full) < 52:
            raise ValueError(f"{bgy}: insufficient history (<52 points). Cannot model.")

        df_train = df_full[df_full["ds"] <= train_end].reset_index(drop=True)
        if len(df_train) < 52:
            raise ValueError(f"{bgy}: training series <52 points. Cannot model.")

        y_true_test = (
            df_full.set_index("ds")
            .reindex(test_ds, fill_value=0)["y"]
            .to_numpy(float)
        )

        rmse_p = np.inf
        pred_p_test = None
        pred_p_fut = None
        ci_p_test = None
        ci_p_fut = None

        if PROPHET_OK:
            try:
                from prophet import Prophet

                mp = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    interval_width=0.95,
                )
                mp.fit(df_train[["ds", "y"]])

                fut = mp.make_future_dataframe(
                    periods=len(test_ds) + horizon,
                    freq="W-MON"
                )
                fp = mp.predict(fut).set_index("ds")

                p_test = fp.reindex(test_ds)
                p_fut = fp.reindex(future_ds)

                pred_p_test = np.clip(p_test["yhat"].to_numpy(float), 0, None)
                pred_p_fut = np.clip(p_fut["yhat"].to_numpy(float), 0, None)

                ci_p_test = np.clip(
                    p_test[["yhat_lower", "yhat_upper"]].to_numpy(float), 0, None
                )
                ci_p_fut = np.clip(
                    p_fut[["yhat_lower", "yhat_upper"]].to_numpy(float), 0, None
                )

                if np.isnan(pred_p_test).any() or np.isnan(pred_p_fut).any():
                    raise ValueError("Prophet produced NaN outputs.")

                rmse_p = float(np.sqrt(mean_squared_error(y_true_test, pred_p_test)))

            except Exception as e:
                print(f"Prophet failed for {bgy}: {e}")
                pred_p_test = None

        rmse_a = np.inf
        pred_a_test = None
        pred_a_fut = None

        try:
            y_train = df_train.set_index("ds")["y"]
            y_train.index = pd.DatetimeIndex(y_train.index, freq="W-MON")

            ma = pm.auto_arima(
                y_train,
                seasonal=True,
                m=52,
                stepwise=True,
                suppress_warnings=True,
                error_action="ignore",
            )

            pred_test = ma.predict(n_periods=len(test_ds))
            pred_future = ma.predict(n_periods=len(test_ds) + horizon)[-horizon:]

            pred_test = np.clip(pred_test.astype(float), 0, None)
            pred_future = np.clip(pred_future.astype(float), 0, None)

            pred_a_test = pred_test
            pred_a_fut = pred_future

            if len(pred_a_test) != len(test_ds):
                raise ValueError("ARIMA test prediction length mismatch.")

            rmse_a = float(np.sqrt(mean_squared_error(y_true_test, pred_a_test)))

        except Exception as e:
            print(f"ARIMA failed for {bgy}: {e}")
            pred_a_test = None

        if pred_p_test is not None and rmse_p <= rmse_a:
            model_used = "Prophet"
            test_vals = pred_p_test
            fut_vals = pred_p_fut
            test_ci = ci_p_test
            fut_ci = ci_p_fut
        else:
            model_used = "ARIMA"
            test_vals = pred_a_test
            fut_vals = pred_a_fut
            test_ci = None
            fut_ci = None

        if test_vals is None or fut_vals is None:
            raise RuntimeError(f"{bgy}: No valid forecast from either model.")

        if abs(test_vals[-1] - fut_vals[0]) > 50:
            print(f"Warning: {bgy} discontinuity detected >50 cases.")

        out_test = pd.DataFrame({
            "Barangay_standardized": bgy,
            "ds": test_ds,
            "local_forecast": test_vals,
        })

        out_fut = pd.DataFrame({
            "Barangay_standardized": bgy,
            "ds": future_ds,
            "local_forecast": fut_vals,
        })

        all_outputs.append(pd.concat([out_test, out_fut], ignore_index=True))

        local_results.append({
            "Barangay": bgy,
            "RMSE_Prophet": rmse_p,
            "RMSE_ARIMA": rmse_a,
            "Chosen": model_used,
        })

        print(f"{bgy}: Train={len(df_train)} | Test={len(test_ds)} | Best={model_used}")

    local_results_df = pd.DataFrame(local_results)
    local_results_df.to_csv(cfg.out / "local_model_performance.csv", index=False)

    local_forecasts_all_df = pd.concat(all_outputs, ignore_index=True)
    local_forecasts_all_df.to_csv(cfg.out / "barangay_local_forecasts.csv", index=False)

    print("✅ Local Tier A models complete.")
    return local_results_df, local_forecasts_all_df
