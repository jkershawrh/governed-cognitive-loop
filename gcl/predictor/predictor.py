from __future__ import annotations

from collections import Counter
from typing import Optional

from gcl.domain.contracts import Evidence, Trajectory, TrajectoryPoint
from gcl.predictor.slo_seed import linear_regression


class HorizonPredictor:
    def predict(self, signals: list[Evidence], horizon_steps: int) -> Trajectory:
        if not signals:
            return self._flat_trajectory(0.0, horizon_steps, confidence=0.0)

        # Check for classification forecast data
        forecast_signals = [s for s in signals if s.source == "classification_metrics"
                            and s.metric == "latency_ms"
                            and s.labels.get("forecast") == "true"]
        if forecast_signals:
            forecast_value = forecast_signals[0].value
            conf = 0.85  # classification-backed predictions are high confidence
            return self._forecast_trajectory(forecast_value, horizon_steps, conf)

        metric_signals = self._select_primary_metric(signals)
        values = [s.value for s in metric_signals]

        if len(values) < 3:
            last = values[-1] if values else 0.0
            return self._flat_trajectory(last, horizon_steps, confidence=0.1)

        if len(values) >= 3:
            spike_peak = self._detect_spike(values)
            if spike_peak is not None:
                return self._spike_trajectory(spike_peak, values, horizon_steps)

        x = list(range(len(values)))
        slope, intercept, r_squared = linear_regression(x, values)

        points: list[TrajectoryPoint] = []
        start = len(values)
        for i in range(horizon_steps):
            step_x = start + i
            predicted = slope * step_x + intercept
            margin = abs(predicted) * (1.0 - r_squared) * 0.1
            points.append(
                TrajectoryPoint(
                    step=i,
                    value=predicted,
                    lower=predicted - margin,
                    upper=predicted + margin,
                )
            )

        mean = sum(values) / len(values)
        if mean > 0:
            cv = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 / mean
        else:
            cv = 1.0
        if cv < 0.15 and len(values) >= 5:
            confidence = max(0.7, min(1.0, len(values) / 10.0))
        elif len(values) >= 10 and mean > 0:
            sample_factor = min(1.0, len(values) / 20.0)
            min_val = min(values)
            if min_val > 0 and mean / min_val < 3:
                confidence = max(0.6, sample_factor * 0.8)
            else:
                confidence = max(r_squared * sample_factor, 0.35 * sample_factor + 0.1)
        else:
            confidence = max(0.0, min(1.0, r_squared * min(len(values) / 10.0, 1.0)))

        return Trajectory(
            points=points,
            horizon_steps=horizon_steps,
            confidence=confidence,
        )

    def _select_primary_metric(self, signals: list[Evidence]) -> list[Evidence]:
        latency = [s for s in signals if s.metric == "latency_ms"]
        if len(latency) >= 3:
            return latency
        counts = Counter(s.metric for s in signals)
        primary = counts.most_common(1)[0][0]
        return [s for s in signals if s.metric == primary]

    def _detect_spike(self, values: list[float]) -> Optional[float]:
        """Detect if values contain a spike. Returns peak value or None."""
        from gcl.config import get_settings
        settings = get_settings()
        mean = sum(values) / len(values)
        if mean <= 0:
            return None
        peak = max(values)
        if peak <= 5000:
            return None
        # Require a significant fraction of values to be far below the peak.
        # This distinguishes true spikes from uniformly noisy data.
        low_count = sum(1 for v in values if v < peak * 0.25)
        if low_count < len(values) * 0.3:
            return None
        non_peak = [v for v in values if v < peak]
        if non_peak:
            baseline = sum(non_peak) / len(non_peak)
        else:
            baseline = mean
        if baseline <= 0:
            return None
        if peak > baseline * settings.spike_detection_threshold:
            return peak
        return None

    def _spike_trajectory(
        self, peak: float, values: list[float], horizon_steps: int
    ) -> Trajectory:
        """Build a trajectory from a detected spike, decaying from peak."""
        decay_rate = 0.9
        points: list[TrajectoryPoint] = []
        for i in range(horizon_steps):
            val = peak * (decay_rate ** i)
            margin = val * 0.1
            points.append(TrajectoryPoint(
                step=i,
                value=val,
                lower=val - margin,
                upper=val + margin,
            ))
        confidence = min(0.85, len(values) / 10.0)
        return Trajectory(
            points=points,
            horizon_steps=horizon_steps,
            confidence=confidence,
        )

    def _forecast_trajectory(
        self, forecast_value: float, horizon_steps: int, confidence: float
    ) -> Trajectory:
        """Build a trajectory from a classification forecast value."""
        points = []
        for i in range(horizon_steps):
            val = forecast_value * (1.0 + i * 0.01)  # slight upward trend from forecast
            margin = val * 0.05
            points.append(TrajectoryPoint(step=i, value=val, lower=val - margin, upper=val + margin))
        return Trajectory(points=points, horizon_steps=horizon_steps, confidence=confidence)

    def _flat_trajectory(
        self, value: float, horizon_steps: int, confidence: float
    ) -> Trajectory:
        points = [TrajectoryPoint(step=i, value=value) for i in range(horizon_steps)]
        return Trajectory(
            points=points,
            horizon_steps=horizon_steps,
            confidence=confidence,
        )
