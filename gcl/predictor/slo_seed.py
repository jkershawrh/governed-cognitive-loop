from __future__ import annotations

import numpy as np


def linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Simple linear regression returning (slope, intercept, r_squared)."""
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)

    n = len(x_arr)
    if n < 2:
        return 0.0, float(y_arr[0]) if n == 1 else 0.0, 0.0

    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)

    ss_xx = np.sum((x_arr - x_mean) ** 2)
    ss_xy = np.sum((x_arr - x_mean) * (y_arr - y_mean))
    ss_yy = np.sum((y_arr - y_mean) ** 2)

    if ss_xx == 0:
        return 0.0, float(y_mean), 0.0

    slope = float(ss_xy / ss_xx)
    intercept = float(y_mean - slope * x_mean)

    if ss_yy == 0:
        r_squared = 1.0
    else:
        r_squared = float((ss_xy ** 2) / (ss_xx * ss_yy))

    return slope, intercept, max(0.0, min(1.0, r_squared))
