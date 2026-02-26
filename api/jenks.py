# api/jenks.py
from __future__ import annotations

from typing import List, Optional, Sequence
import math

LABELS_5 = ["very_low", "low", "medium", "high", "very_high"]


def jenks_breaks(values: Sequence[float], n_classes: int = 5) -> List[float]:
    """
    Jenks natural breaks for 1D data.
    Returns breakpoints length n_classes+1: [min, ..., max].
    """
    data = sorted(float(v) for v in values if v is not None)
    n = len(data)
    if n == 0:
        return [0.0] * (n_classes + 1)
    if n_classes <= 1:
        return [data[0], data[-1]]

    lower = [[0] * (n_classes + 1) for _ in range(n + 1)]
    var = [[0.0] * (n_classes + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        lower[i][1] = 1
        var[i][1] = 0.0

    for j in range(2, n_classes + 1):
        for i in range(1, n + 1):
            var[i][j] = float("inf")

    for l in range(2, n + 1):
        s1 = s2 = w = 0.0
        v = 0.0
        for m in range(1, l + 1):
            i3 = l - m + 1
            val = data[i3 - 1]
            s2 += val * val
            s1 += val
            w += 1.0
            v = s2 - (s1 * s1) / w
            i4 = i3 - 1
            if i4 != 0:
                for j in range(2, n_classes + 1):
                    cand = v + var[i4][j - 1]
                    if var[l][j] >= cand:
                        lower[l][j] = i3
                        var[l][j] = cand
        lower[l][1] = 1
        var[l][1] = v

    k = n
    kclass = [0.0] * (n_classes + 1)
    kclass[n_classes] = data[-1]
    kclass[0] = data[0]

    count = n_classes
    while count > 1:
        idx = lower[k][count] - 1
        kclass[count - 1] = data[idx]
        k = lower[k][count] - 1
        count -= 1

    return kclass


def jenks_breaks_safe(values: Sequence[float], n_classes: int = 5) -> List[float]:
    data = [float(v) for v in values if v is not None]
    if not data:
        return [0.0] * (n_classes + 1)
    if max(data) == min(data):
        return [data[0]] * (n_classes + 1)
    return jenks_breaks(data, n_classes=n_classes)


def jenks_class(value: Optional[float], breaks: Sequence[float]) -> str:
    if value is None:
        return "unknown"

    b = list(breaks)
    if len(b) < 2:
        return "unknown"

    for i in range(1, len(b)):
        if b[i] < b[i - 1]:
            b[i] = b[i - 1]

    for i in range(1, len(b)):
        if value <= b[i]:
            return LABELS_5[min(i - 1, len(LABELS_5) - 1)]
    return "very_high"