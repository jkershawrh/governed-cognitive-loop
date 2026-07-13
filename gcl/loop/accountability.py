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
                      latency_at_commit: float, fleet_response: Optional[dict] = None,
                      outcome_eligible: bool = True):
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

        # Proposal acceptance is not execution. Outcome checks begin only after an
        # externally verified outcome receipt has been supplied.
        fleet_status = ""
        execution_verified = False
        if fleet_response and isinstance(fleet_response, dict):
            fleet_status = fleet_response.get("status", "")
            execution_verified = fleet_response.get("execution_verified") is True

        if fleet_status in ("refused", "rejected"):
            return
        if fleet_response is not None and not execution_verified:
            outcome_eligible = False
        if not outcome_eligible:
            return

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

    async def verify_actuation(self, fleet_url: str, fleet_token: str,
                                action_type: str, intended_params: dict) -> dict:
        """Check if the physical infrastructure matches the intent."""
        if action_type not in ("scale", "pre_warm"):
            return {"skipped": True, "reason": "non-scaling action"}

        if not fleet_url:
            return {"skipped": True, "reason": "no fleet URL configured"}

        intended_replicas = intended_params.get("replicas", intended_params.get("target_replicas"))
        if intended_replicas is None:
            return {"skipped": True, "reason": "no replica count in intent"}

        try:
            import httpx
            from gcl.adapter.fleet_adapter import _generate_fleet_token
            headers = {}
            if fleet_token:
                headers["Authorization"] = f"Bearer {_generate_fleet_token(fleet_token)}"

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{fleet_url}/api/v1/modelplane/deployments", headers=headers)
                if r.status_code != 200:
                    return {"skipped": True, "reason": f"fleet returned {r.status_code}"}

                deployments = r.json()
                # Sum replicas across all deployments (simplified)
                actual_replicas = 0
                if isinstance(deployments, list):
                    for d in deployments:
                        actual_replicas += d.get("replicas", d.get("spec", {}).get("replicas", 0))

                return {
                    "verified": actual_replicas >= intended_replicas,
                    "intended_replicas": intended_replicas,
                    "actual_replicas": actual_replicas,
                }
        except Exception as e:
            return {"skipped": True, "reason": str(e)}
