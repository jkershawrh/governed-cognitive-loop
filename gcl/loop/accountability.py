from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from gcl.config import get_settings
from gcl.domain.contracts import Evidence


@dataclass
class CommitRecord:
    action_type: str
    committed_at: float
    cycle_id: str
    correlation_id: str
    latency_at_commit: float
    fleet_response: Optional[dict] = None


@dataclass
class PendingOutcome:
    commit: CommitRecord
    expected_metric: str = "latency_ms"
    expected_direction: str = "decrease"  # decrease for scale/pre_warm, stable for shed_load


@dataclass
class OutcomeRecord:
    commit: CommitRecord
    metric_before: float
    metric_after: float
    effective: bool
    elapsed_ms: float


# Map action types to expected metric behavior
ACTION_EXPECTATIONS = {
    "scale": ("latency_ms", "decrease"),
    "pre_warm": ("latency_ms", "decrease"),
    "shed_load": ("latency_ms", "stable"),
    "alert": (None, None),  # no metric expectation
    "migrate": (None, None),
    "no_action": (None, None),
    "rollback": (None, None),
}


class AccountabilityTracker:
    def __init__(self):
        self._recent_commits: list[CommitRecord] = []
        self._pending_outcomes: list[PendingOutcome] = []
        self._outcome_min_age_seconds: float = 30.0

    def can_commit(self, action_type: str) -> tuple[bool, str]:
        settings = get_settings()
        if settings.decision_cooldown_seconds <= 0:
            return True, ""
        now = time.time()
        for record in reversed(self._recent_commits):
            if record.action_type == action_type:
                elapsed = now - record.committed_at
                if elapsed < settings.decision_cooldown_seconds:
                    return False, f"cooldown: {action_type} committed {elapsed:.0f}s ago (min {settings.decision_cooldown_seconds}s)"
                break
        return True, ""

    def record_commit(self, cycle_id: str, correlation_id: str, action_type: str,
                      latency_at_commit: float, fleet_response: Optional[dict] = None):
        record = CommitRecord(
            action_type=action_type,
            committed_at=time.time(),
            cycle_id=cycle_id,
            correlation_id=correlation_id,
            latency_at_commit=latency_at_commit,
            fleet_response=fleet_response,
        )
        self._recent_commits.append(record)
        # Keep only last 100 records
        if len(self._recent_commits) > 100:
            self._recent_commits = self._recent_commits[-100:]

        # Only track outcome if fleet accepted (or no fleet configured)
        fleet_status = ""
        if fleet_response and isinstance(fleet_response, dict):
            fleet_status = fleet_response.get("status", "")

        if fleet_status == "refused":
            return  # Do not track outcome for refused intents

        metric, direction = ACTION_EXPECTATIONS.get(action_type, (None, None))
        if metric is not None:
            self._pending_outcomes.append(PendingOutcome(
                commit=record,
                expected_metric=metric,
                expected_direction=direction,
            ))
            settings = get_settings()
            if len(self._pending_outcomes) > settings.max_pending_outcomes:
                self._pending_outcomes = self._pending_outcomes[-settings.max_pending_outcomes:]

    def check_outcomes(self, evidence: list[Evidence]) -> list[OutcomeRecord]:
        now = time.time()
        results: list[OutcomeRecord] = []
        still_pending: list[PendingOutcome] = []

        for pending in self._pending_outcomes:
            elapsed = now - pending.commit.committed_at
            if elapsed < self._outcome_min_age_seconds:
                still_pending.append(pending)
                continue

            # Find the current metric value
            current_value = None
            for e in evidence:
                if e.metric == pending.expected_metric:
                    current_value = e.value
                    break

            if current_value is None:
                still_pending.append(pending)
                continue

            before = pending.commit.latency_at_commit
            after = current_value

            if pending.expected_direction == "decrease":
                effective = after < before
            elif pending.expected_direction == "stable":
                effective = after <= before * 1.1  # within 10%
            else:
                effective = True

            results.append(OutcomeRecord(
                commit=pending.commit,
                metric_before=before,
                metric_after=after,
                effective=effective,
                elapsed_ms=elapsed * 1000,
            ))

        self._pending_outcomes = still_pending
        return results

    def pending_count(self) -> int:
        return len(self._pending_outcomes)
