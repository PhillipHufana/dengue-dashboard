from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def smape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred)
    with np.errstate(divide="ignore", invalid="ignore"):
        v = 2 * np.abs(y_pred - y_true) / denom
        v[np.isnan(v)] = 0.0
    return float(np.mean(v))

def plot_and_save(fig_path: Path) -> None:
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150)
    plt.close()
