from __future__ import annotations

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
    def test_trending_up_produces_rising_trajectory(self, predictor):
        signals = [Evidence(metric="latency_ms", value=3000 + i * 100) for i in range(20)]
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
        signals = [Evidence(metric="latency_ms", value=random.uniform(1000, 9000)) for _ in range(20)]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert trajectory.confidence < 0.5

    def test_insufficient_data_returns_flat_low_confidence(self, predictor):
        signals = [Evidence(metric="latency_ms", value=5000.0)]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert trajectory.confidence < 0.3
        for p in trajectory.points:
            assert p.value == 5000.0

    def test_confidence_bounded_0_to_1(self, predictor):
        signals = [Evidence(metric="latency_ms", value=3000 + i * 100) for i in range(30)]
        trajectory = predictor.predict(signals, horizon_steps=10)
        assert 0.0 <= trajectory.confidence <= 1.0

    def test_trajectory_length_matches_horizon(self, predictor):
        signals = [Evidence(metric="latency_ms", value=3000 + i * 50) for i in range(15)]
        for horizon in [5, 10, 20]:
            trajectory = predictor.predict(signals, horizon_steps=horizon)
            assert len(trajectory.points) == horizon
            assert trajectory.horizon_steps == horizon

    def test_empty_signals(self, predictor):
        trajectory = predictor.predict([], horizon_steps=5)
        assert trajectory.confidence == 0.0
        assert len(trajectory.points) == 5

    def test_two_data_points(self, predictor):
        signals = [
            Evidence(metric="latency_ms", value=3000.0),
            Evidence(metric="latency_ms", value=4000.0),
        ]
        trajectory = predictor.predict(signals, horizon_steps=5)
        assert trajectory.confidence < 0.3
        for p in trajectory.points:
            assert p.value == 4000.0
