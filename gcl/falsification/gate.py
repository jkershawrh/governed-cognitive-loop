from __future__ import annotations

from uuid import uuid4

from gcl.domain.contracts import (
    ActionStep,
    Constraint,
    Evidence,
    FalsificationResult,
    Trajectory,
)
from gcl.domain.enums import Verdict
from gcl.falsification.checks import (
    check_capacity_available,
    check_compliance_action_valid,
    check_migration_target_available,
    check_prediction_confidence,
    check_shed_load_bounded,
    check_warmup_time_realistic,
)
from gcl.falsification.llm_adversary import LLMAdversary
from gcl.inference.client import get_force_rules


class FalsificationGate:
    def __init__(self):
        self._adversary = LLMAdversary()

    async def falsify(
        self,
        action_step: ActionStep,
        trajectory: Trajectory,
        constraints: list[Constraint],
        evidence: list[Evidence],
    ) -> FalsificationResult:
        action_id = uuid4()
        evidence_ids = [e.id for e in evidence]

        capacity_fail = check_capacity_available(action_step, evidence, constraints)
        if capacity_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="capacity_overcommit",
                reasoning=capacity_fail,
                evidence_ids=evidence_ids,
            )

        warmup_fail = check_warmup_time_realistic(action_step, evidence)
        if warmup_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="warmup_time_unrealistic",
                reasoning=warmup_fail,
                evidence_ids=evidence_ids,
            )

        confidence_fail = check_prediction_confidence(action_step, trajectory)
        if confidence_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="low_prediction_confidence",
                reasoning=confidence_fail,
                evidence_ids=evidence_ids,
            )

        compliance_fail = check_compliance_action_valid(action_step, evidence, constraints)
        if compliance_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="compliance_action_invalid",
                reasoning=compliance_fail,
                evidence_ids=evidence_ids,
            )

        shed_fail = check_shed_load_bounded(action_step, evidence, constraints)
        if shed_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="shed_load_unbounded",
                reasoning=shed_fail,
                evidence_ids=evidence_ids,
            )

        migrate_fail = check_migration_target_available(action_step, evidence, constraints)
        if migrate_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="migration_target_missing",
                reasoning=migrate_fail,
                evidence_ids=evidence_ids,
            )

        if not get_force_rules():
            context = {
                "trajectory_confidence": trajectory.confidence,
                "constraints_count": len(constraints),
                "evidence_count": len(evidence),
            }
            adversary_reason = await self._adversary.probe(action_step, context)
            if adversary_reason is not None:
                return FalsificationResult(
                    action_id=action_id,
                    verdict=Verdict.FAILS,
                    failed_check="llm_adversarial_probe",
                    reasoning=adversary_reason,
                    evidence_ids=evidence_ids,
                )

        return FalsificationResult(
            action_id=action_id,
            verdict=Verdict.SURVIVES,
            reasoning="All deterministic checks passed.",
            evidence_ids=evidence_ids,
        )
