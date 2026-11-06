"""Rolling z-score anomaly detector. Pure stdlib - no numpy."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# History needs at least this many points before the current one to compute a mean/stdev worth
# trusting. Below that, detect() reports "not an anomaly" rather than raising - a thin window is
# normal right after startup and should not crash a run.
MIN_HISTORY_POINTS = 2


@dataclass(frozen=True)
class DetectionResult:
    value: float
    mean: float
    stdev: float
    z_score: float
    expected_low: float
    expected_high: float
    is_anomaly: bool


def detect(window: list[float], threshold: float) -> DetectionResult:
    """Check whether the last point in `window` is an anomaly against the points before it.

    `window` is ordered oldest-to-newest. The last value is judged against the mean/stdev of
    everything before it, not against itself.
    """
    if len(window) < MIN_HISTORY_POINTS + 1:
        value = window[-1] if window else 0.0
        return DetectionResult(value, value, 0.0, 0.0, value, value, False)

    *history, value = window
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history)

    if stdev == 0:
        is_anomaly = value != mean
        z_score = float("inf") if is_anomaly else 0.0
        return DetectionResult(value, mean, stdev, z_score, mean, mean, is_anomaly)

    z_score = (value - mean) / stdev
    expected_low = mean - threshold * stdev
    expected_high = mean + threshold * stdev
    is_anomaly = abs(z_score) >= threshold

    return DetectionResult(value, mean, stdev, z_score, expected_low, expected_high, is_anomaly)
