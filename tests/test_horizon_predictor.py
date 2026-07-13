from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gcl.domain.contracts import Evidence
from gcl.predictor.predictor import HorizonPredictor
from gcl.predictor.slo_seed import linear_regression


@pytest.fixture
def predictor():
    return HorizonPredictor()


class TestLinearRegression:
    def test_perfect_line(self):
        slope, intercept, r2 = linear_regression([0, 1, 2, 3], [0, 2, 4, 6])
        assert abs(slope - 2.0) < 1e-10
        assert abs(intercept) < 1e-10
        assert abs(r2 - 1.0) < 1e-10

    def test_flat_line(self):
        slope, intercept, r2 = linear_regression([0, 1, 2, 3], [5, 5, 5, 5])
        assert abs(slope) < 1e-10
        assert abs(intercept - 5.0) < 1e-10

    def test_single_point(self):
        slope, intercept, r2 = linear_regression([0], [10])
        assert slope == 0.0
        assert intercept == 10.0


class TestHorizonPredictor:
    def test_uses_exact_deepfield_forecast_confidence_without_fabricating_samples(
        self,
        predictor,
    ):
        generated_at = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        signal = Evidence(
            metric="latency_ms",
            value=7000.0,
            timestamp=generated_at,
            source="deepfield-fleet",
            metadata={
                "producer_event_type": "io.srex.deepfield.forecast.v1",
                "producer_data": {
                    "predicted_value": 7000.0,
                    "confidence": 0.82,
                    "horizon_seconds": 120,
                    "advisory_only": True,
                },
            },
        )

        trajectory = predictor.predict([signal], horizon_steps=10)

        assert trajectory.confidence == 0.82
        assert trajectory.generated_at == generated_at
        assert trajectory.horizon_steps == 1
        assert [point.value for point in trajectory.points] == [7000.0]

    def test_trending_up_produces_rising_trajectory(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000 + i * 100) for i in range(20)
        ]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert len(trajectory.points) == 10
        for i in range(1, len(trajectory.points)):
            assert trajectory.points[i].value > trajectory.points[i - 1].value

    def test_flat_signal_produces_flat_trajectory(self, predictor):
        signals = [Evidence(metric="latency_ms", value=5000.0) for _ in range(20)]
        trajectory = predictor.predict(signals, horizon_steps=10)
        for p in trajectory.points:
            assert abs(p.value - 5000.0) < 1.0

    def test_noisy_signal_produces_low_confidence(self, predictor):
        import random

        random.seed(42)
        signals = [
            Evidence(metric="latency_ms", value=random.uniform(1000, 9000))
            for _ in range(20)
        ]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert trajectory.confidence < 0.5

    def test_insufficient_data_returns_flat_low_confidence(self, predictor):
        signals = [Evidence(metric="latency_ms", value=5000.0)]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert trajectory.confidence < 0.3
        for p in trajectory.points:
            assert p.value == 5000.0

    def test_confidence_bounded_0_to_1(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000 + i * 100) for i in range(30)
        ]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert 0.0 <= trajectory.confidence <= 1.0

    def test_trajectory_length_matches_horizon(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000 + i * 50) for i in range(15)
        ]
        for horizon in [5, 10, 20]:
            trajectory = predictor.predict(signals, horizon_steps=horizon)
            assert len(trajectory.points) == horizon
            assert trajectory.horizon_steps == horizon

    def test_empty_signals(self, predictor):
        trajectory = predictor.predict([], horizon_steps=5)
        assert trajectory.confidence == 0.0
        assert len(trajectory.points) == 5

    def test_spike_detection(self, predictor):
        """Spike pattern should produce trajectory reflecting peak, not average."""
        signals = [Evidence(metric="latency_ms", value=10000.0) for _ in range(5)] + [
            Evidence(metric="latency_ms", value=500.0) for _ in range(5)
        ]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert trajectory.points[0].value > 5000, (
            f"Spike not detected: first point={trajectory.points[0].value}, expected > 5000"
        )

    def test_latency_ms_preferred_over_other_metrics(self, predictor):
        """When latency_ms signals are present, prefer them over other metrics."""
        signals = [
            Evidence(metric="latency_ms", value=3000.0 + i * 100) for i in range(5)
        ] + [
            Evidence(metric="slo_breach_severity", value=0.5 + i * 0.05)
            for i in range(10)
        ]
        trajectory = predictor.predict(signals, horizon_steps=5)
        # Trajectory should be in the 3000-4000 range (latency), not 0.5-1.0 (severity)
        assert trajectory.points[0].value > 100, (
            f"Predictor used wrong metric: value={trajectory.points[0].value}"
        )

    def test_no_spike_on_normal_data(self, predictor):
        """Normal data should use regression, not spike detection."""
        signals = [Evidence(metric="latency_ms", value=3000.0) for _ in range(10)]
        trajectory = predictor.predict(signals, horizon_steps=5)
        # Should be close to 3000, not inflated
        assert abs(trajectory.points[0].value - 3000) < 500

    def test_two_data_points(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000.0),
            Evidence(metric="latency_ms", value=4000.0),
        ]
        trajectory = predictor.predict(signals, horizon_steps=5)
        assert trajectory.confidence < 0.3
        for p in trajectory.points:
            assert p.value == 4000.0

    def test_predictor_uses_forecast_value_when_available(self, predictor):
        signals = [
            Evidence(
                metric="latency_ms",
                value=6200.0,
                source="classification_metrics",
                labels={"forecast": "true", "contributing_to": "slo_breach_predicted"},
            ),
            Evidence(metric="latency_ms", value=5000.0, source="prometheus"),
            Evidence(metric="latency_ms", value=5100.0, source="prometheus"),
            Evidence(metric="latency_ms", value=5200.0, source="prometheus"),
        ]
        trajectory = predictor.predict(signals, horizon_steps=5)
        # Should use the 6200 forecast, not regress on 5000-5200
        assert trajectory.points[0].value > 6000

    def test_predictor_falls_back_to_regression_without_forecast(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000.0 + i * 100) for i in range(10)
        ]
        trajectory = predictor.predict(signals, horizon_steps=5)
        # Should use regression (no forecast signal)
        assert trajectory.points[0].value > 3000
        assert trajectory.points[0].value < 6000
