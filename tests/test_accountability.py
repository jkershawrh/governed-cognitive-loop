from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from gcl.loop.accountability import AccountabilityTracker, CommitRecord
from gcl.domain.contracts import Evidence


@pytest.fixture
def tracker():
    return AccountabilityTracker()


class TestCooldown:
    def test_cooldown_blocks_same_action(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        allowed, reason = tracker.can_commit("scale")
        assert not allowed
        assert "cooldown" in reason

    def test_cooldown_allows_different_action(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        allowed, reason = tracker.can_commit("alert")
        assert allowed

    def test_cooldown_expires(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        # Manually backdate the commit
        tracker._recent_commits[-1].committed_at = time.time() - 120
        allowed, reason = tracker.can_commit("scale")
        assert allowed

    def test_cooldown_disabled_when_zero(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        with patch("gcl.loop.accountability.get_settings") as mock:
            mock.return_value.decision_cooldown_seconds = 0
            mock.return_value.max_pending_outcomes = 10
            allowed, _ = tracker.can_commit("scale")
        assert allowed


class TestOutcomes:
    def test_outcome_effective_when_latency_drops(self, tracker):
        tracker._outcome_min_age_seconds = 0
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        evidence = [Evidence(metric="latency_ms", value=3500.0)]
        outcomes = tracker.check_outcomes(evidence)
        assert len(outcomes) == 1
        assert outcomes[0].effective is True
        assert outcomes[0].metric_before == 8000.0
        assert outcomes[0].metric_after == 3500.0

    def test_outcome_ineffective_when_latency_unchanged(self, tracker):
        tracker._outcome_min_age_seconds = 0
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        evidence = [Evidence(metric="latency_ms", value=8500.0)]
        outcomes = tracker.check_outcomes(evidence)
        assert len(outcomes) == 1
        assert outcomes[0].effective is False

    def test_outcome_not_checked_before_min_age(self, tracker):
        tracker._outcome_min_age_seconds = 9999
        tracker.record_commit("c1", "corr1", "scale", 8000.0)
        evidence = [Evidence(metric="latency_ms", value=3500.0)]
        outcomes = tracker.check_outcomes(evidence)
        assert len(outcomes) == 0
        assert tracker.pending_count() == 1


class TestFleetResponse:
    def test_fleet_response_tracked(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0,
                            fleet_response={"status": "executed", "intent_id": "i1"})
        assert tracker._recent_commits[-1].fleet_response["status"] == "executed"
        assert tracker.pending_count() == 1

    def test_fleet_refused_prevents_outcome(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0,
                            fleet_response={"status": "refused", "reason": "policy"})
        assert tracker.pending_count() == 0

    def test_fleet_deferred_tracked(self, tracker):
        tracker.record_commit("c1", "corr1", "scale", 8000.0,
                            fleet_response={"status": "deferred"})
        assert tracker.pending_count() == 1

    def test_pending_outcomes_capped(self, tracker):
        with patch("gcl.loop.accountability.get_settings") as mock:
            mock.return_value.decision_cooldown_seconds = 0
            mock.return_value.max_pending_outcomes = 3
            for i in range(10):
                tracker.record_commit(f"c{i}", f"corr{i}", "scale", 8000.0)
        assert tracker.pending_count() <= 3

    def test_no_action_has_no_pending(self, tracker):
        tracker.record_commit("c1", "corr1", "no_action", 3000.0)
        assert tracker.pending_count() == 0

    def test_alert_has_no_pending(self, tracker):
        tracker.record_commit("c1", "corr1", "alert", 3000.0)
        assert tracker.pending_count() == 0
