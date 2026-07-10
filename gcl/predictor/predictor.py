from __future__ import annotations

from collections import Counter

from gcl.domain.contracts import Evidence, Trajectory, TrajectoryPoint
from gcl.predictor.slo_seed import linear_regression


class HorizonPredictor:
    def predict(self, signals: list[Evidence], horizon_steps: int) -> Trajectory:
        if not signals:
            return self._flat_trajectory(0.0, horizon_steps, confidence=0.0)

        metric_signals = self._select_primary_metric(signals)
        values = [s.value for s in metric_signals]

        if len(values) < 3:
            last = values[-1] if values else 0.0
            return self._flat_trajectory(last, horizon_steps, confidence=0.1)

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

        confidence = max(0.0, min(1.0, r_squared * min(len(values) / 10.0, 1.0)))

        return Trajectory(
            points=points,
            horizon_steps=horizon_steps,
            confidence=confidence,
        )

    def _select_primary_metric(self, signals: list[Evidence]) -> list[Evidence]:
        counts = Counter(s.metric for s in signals)
        primary = counts.most_common(1)[0][0]
        return [s for s in signals if s.metric == primary]

    def _flat_trajectory(
        self, value: float, horizon_steps: int, confidence: float
    ) -> Trajectory:
        points = [TrajectoryPoint(step=i, value=value) for i in range(horizon_steps)]
        return Trajectory(
            points=points,
            horizon_steps=horizon_steps,
            confidence=confidence,
        )
