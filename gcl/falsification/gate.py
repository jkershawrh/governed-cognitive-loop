from __future__ import annotations

from uuid import uuid4

from gcl.domain.contracts import (
    ActionStep,
    Constraint,
    Evidence,
    FalsificationResult,
    Trajectory,
)
from gcl.domain.enums import AdversaryStatus, Verdict
from gcl.falsification.checks import (
    check_capacity_available,
    check_compliance_action_valid,
    check_migration_target_available,
    check_prediction_confidence,
    check_scale_magnitude_reasonable,
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
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        magnitude_fail = check_scale_magnitude_reasonable(action_step, evidence, constraints)
        if magnitude_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="scale_magnitude_unreasonable",
                reasoning=magnitude_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        warmup_fail = check_warmup_time_realistic(action_step, evidence)
        if warmup_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="warmup_time_unrealistic",
                reasoning=warmup_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        confidence_fail = check_prediction_confidence(action_step, trajectory)
        if confidence_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="low_prediction_confidence",
                reasoning=confidence_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        compliance_fail = check_compliance_action_valid(action_step, evidence, constraints)
        if compliance_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="compliance_action_invalid",
                reasoning=compliance_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        shed_fail = check_shed_load_bounded(action_step, evidence, constraints)
        if shed_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="shed_load_unbounded",
                reasoning=shed_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        migrate_fail = check_migration_target_available(action_step, evidence, constraints)
        if migrate_fail is not None:
            return FalsificationResult(
                action_id=action_id,
                verdict=Verdict.FAILS,
                failed_check="migration_target_missing",
                reasoning=migrate_fail,
                evidence_ids=evidence_ids,
                adversary_status=AdversaryStatus.NOT_REACHED,
            )

        adversary_status = AdversaryStatus.SKIPPED_RULES_MODE
        if not get_force_rules():
            context = {
                "trajectory_confidence": trajectory.confidence,
                "constraints_count": len(constraints),
                "evidence_count": len(evidence),
            }
            adversary_reason, adversary_status = await self._adversary.probe(
                action_step, context
            )
            if adversary_reason is not None:
                return FalsificationResult(
                    action_id=action_id,
                    verdict=Verdict.FAILS,
                    failed_check="llm_adversarial_probe",
                    reasoning=adversary_reason,
                    evidence_ids=evidence_ids,
                    adversary_status=adversary_status,
                )

        return FalsificationResult(
            action_id=action_id,
            verdict=Verdict.SURVIVES,
            reasoning=_survival_reasoning(adversary_status),
            evidence_ids=evidence_ids,
            adversary_status=adversary_status,
        )


def _survival_reasoning(status: AdversaryStatus) -> str:
    """Say which gates ran, so the record is not silently ambiguous."""
    if status == AdversaryStatus.PROBED:
        return "All deterministic checks passed and the LLM adversary raised no objection."
    if status == AdversaryStatus.SKIPPED_RULES_MODE:
        return "All deterministic checks passed. LLM adversary skipped: deterministic rules mode."
    if status == AdversaryStatus.UNAVAILABLE:
        return "All deterministic checks passed. LLM adversary unavailable: no usable inference response."
    return "All deterministic checks passed."
