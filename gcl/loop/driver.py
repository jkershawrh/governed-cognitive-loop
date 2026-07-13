from __future__ import annotations

from typing import Optional
from uuid import uuid4

from gcl.adapter.proposer_adapter import ProposerAdapter
from gcl.classifier.classifier import ConstraintClassifier
from gcl.committer.committer import Committer
from gcl.config import decision_signing_key, get_settings
from gcl.controller.controller import Controller
from gcl.domain.contracts import ActionPlan, ActionStep, Evidence, FalsificationResult, LoopCycle
from gcl.domain.enums import Verdict
from gcl.domain.decision_package import (
    ACTION_CLASS_NAMES,
    ProposerIdentity,
    build_decision_package,
)
from gcl.falsification.gate import FalsificationGate
from gcl.interpreter.interpreter import ObjectiveInterpreter
from gcl.loop.accountability import AccountabilityTracker
from gcl.loop.ledger import LedgerClient
from gcl.predictor.predictor import HorizonPredictor


class LoopDriver:
    def __init__(
        self,
        classifier: Optional[ConstraintClassifier] = None,
        predictor: Optional[HorizonPredictor] = None,
        interpreter: Optional[ObjectiveInterpreter] = None,
        controller: Optional[Controller] = None,
        gate: Optional[FalsificationGate] = None,
        committer: Optional[Committer] = None,
        ledger: Optional[LedgerClient] = None,
        adapter: Optional[object] = None,
        accountability: Optional[AccountabilityTracker] = None,
    ):
        self._classifier = classifier or ConstraintClassifier()
        self._predictor = predictor or HorizonPredictor()
        self._interpreter = interpreter or ObjectiveInterpreter()
        self._controller = controller or Controller()
        self._gate = gate or FalsificationGate()
        self._committer = committer or Committer()
        self._ledger = ledger or LedgerClient()
        self._adapter = adapter or ProposerAdapter()
        self._accountability = accountability or AccountabilityTracker()

    async def run_cycle(self, signals: list[Evidence]) -> LoopCycle:
        settings = get_settings()
        correlation_id = f"gcl-{uuid4()}"

        await self._ledger.write_entry(
            "gcl.cycle_start",
            {"cycle_correlation_id": correlation_id},
            correlation_id,
        )

        # Check outcomes from previous commits
        outcomes = self._accountability.check_outcomes(signals)
        for outcome in outcomes:
            await self._ledger.write_entry(
                "gcl.outcome",
                {
                    "action_type": outcome.commit.action_type,
                    "cycle_id": outcome.commit.cycle_id,
                    "metric_before": outcome.metric_before,
                    "metric_after": outcome.metric_after,
                    "effective": outcome.effective,
                    "elapsed_ms": outcome.elapsed_ms,
                },
                correlation_id,
            )

        constraints = await self._classifier.classify(signals)
        await self._ledger.write_entry(
            "gcl.classify",
            {"constraints": [c.model_dump(mode="json") for c in constraints]},
            correlation_id,
        )

        trajectory = self._predictor.predict(signals, settings.horizon_length)
        await self._ledger.write_entry(
            "gcl.predict",
            trajectory.model_dump(mode="json"),
            correlation_id,
        )

        objective = await self._interpreter.interpret(
            {"signals_count": len(signals)},
            constraints,
        )
        await self._ledger.write_entry(
            "gcl.interpret",
            objective.model_dump(mode="json"),
            correlation_id,
        )

        action_plan = self._controller.optimize(trajectory, objective, constraints)
        await self._ledger.write_entry(
            "gcl.plan",
            action_plan.model_dump(mode="json") if action_plan else {"infeasible": True},
            correlation_id,
        )

        if action_plan is None:
            await self._ledger.write_entry(
                "gcl.reject",
                {"reason": "infeasible", "detail": "Controller returned no feasible plan."},
                correlation_id,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=None,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )

        committed_step = action_plan.steps[action_plan.committed_step_index]

        if committed_step.action_type == "no_action":
            await self._ledger.write_entry(
                "gcl.no_action",
                {"reason": "controller selected no consequential fleet action"},
                correlation_id,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=action_plan,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )
        if committed_step.action_type not in ACTION_CLASS_NAMES:
            await self._ledger.write_entry(
                "gcl.reject",
                {
                    "action_type": committed_step.action_type,
                    "reason": "action does not map to a canonical ARE fleet action class",
                },
                correlation_id,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=action_plan,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )

        # Check cooldown before committing
        can_commit, cooldown_reason = self._accountability.can_commit(committed_step.action_type)
        if not can_commit:
            await self._ledger.write_entry(
                "gcl.cooldown",
                {"action_type": committed_step.action_type, "reason": cooldown_reason},
                correlation_id,
            )
            # Override to no_action
            no_op_step = ActionStep(
                step_index=0,
                action_type="no_action",
                parameters={"cooldown_reason": cooldown_reason},
            )
            no_op_plan = ActionPlan(
                steps=[no_op_step] + [
                    ActionStep(step_index=i, action_type="no_action", parameters={})
                    for i in range(1, action_plan.horizon_steps)
                ],
                committed_step_index=0,
                horizon_steps=action_plan.horizon_steps,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=no_op_plan,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )

        # Passport verification: check scope with ARE Foundation
        from gcl.loop.passport import verify_passport
        passport = await verify_passport(committed_step.action_type)
        if passport.get("decision") != "ALLOW":
            await self._ledger.write_entry(
                "gcl.passport_denied",
                {
                    "action_type": committed_step.action_type,
                    "reason": passport.get("reason", ""),
                    "passport_status": passport.get("passport_status", ""),
                },
                correlation_id,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=action_plan,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )

        # Authority gate: check with agent-promotion-line
        from gcl.loop.authority import check_authority
        authority = await check_authority(committed_step.action_type, correlation_id)
        if authority.get("verdict") != "allow":
            await self._ledger.write_entry(
                "gcl.authority_refused",
                {
                    "action_type": committed_step.action_type,
                    "consequence_score": authority.get("consequence_score", 0),
                    "ceiling": authority.get("ceiling", 0),
                    "reason": authority.get("reason", ""),
                },
                correlation_id,
            )
            return LoopCycle(
                constraints_snapshot=constraints,
                trajectory=trajectory,
                objective=objective,
                action_plan=action_plan,
                falsification=None,
                committed=False,
                correlation_id=correlation_id,
            )

        falsification = await self._gate.falsify(
            committed_step, trajectory, constraints, signals,
        )
        await self._ledger.write_entry(
            "gcl.falsify",
            falsification.model_dump(mode="json"),
            correlation_id,
        )

        decision_package = None
        if falsification.verdict == Verdict.SURVIVES:
            try:
                decision_package = build_decision_package(
                    constraints=constraints,
                    action_plan=action_plan,
                    trajectory=trajectory,
                    falsification=falsification,
                    evidence=signals,
                    correlation_id=correlation_id,
                    passport_decision=passport,
                    authority_decision=authority,
                    proposer=ProposerIdentity(
                        agent_id=settings.authority_agent_id,
                        workload_identity=settings.proposer_workload_identity,
                        trust_domain=settings.proposer_trust_domain,
                    ),
                    passport_id=(
                        settings.passport_id
                        or str(passport.get("passport_id", "standalone-test"))
                    ),
                    tenant=settings.default_tenant,
                    zone=settings.default_zone,
                    ttl_seconds=settings.decision_package_ttl_seconds,
                    signing_key=decision_signing_key(settings),
                    signing_key_id=settings.decision_signing_key_id,
                )
            except ValueError as exc:
                await self._ledger.write_entry(
                    "gcl.decision_package_rejected",
                    {
                        "action_type": committed_step.action_type,
                        "reason": str(exc),
                        "execution_verified": False,
                    },
                    correlation_id,
                )
                return LoopCycle(
                    constraints_snapshot=constraints,
                    trajectory=trajectory,
                    objective=objective,
                    action_plan=action_plan,
                    falsification=falsification,
                    committed=False,
                    correlation_id=correlation_id,
                    execution_verified=False,
                )

        commit_result = await self._committer.commit(
            committed_step,
            falsification,
            self._adapter,
            self._ledger,
            correlation_id,
            decision_package=decision_package,
        )

        did_commit = commit_result["committed"]
        fleet_response = commit_result["fleet_response"]

        # Extract primary latency from signals
        latency_at_commit = 0.0
        for s in signals:
            if s.metric == "latency_ms":
                latency_at_commit = s.value
                break

        # Record the commit for accountability tracking
        if did_commit:
            self._accountability.record_commit(
                cycle_id=str(correlation_id),
                correlation_id=correlation_id,
                action_type=committed_step.action_type,
                latency_at_commit=latency_at_commit,
                fleet_response=fleet_response,
                outcome_eligible=False,
            )

        return LoopCycle(
            constraints_snapshot=constraints,
            trajectory=trajectory,
            objective=objective,
            action_plan=action_plan,
            falsification=falsification,
            committed=did_commit,
            fleet_response=fleet_response,
            proposal_response=commit_result["proposal_response"],
            decision_package_digest=commit_result["decision_package_digest"],
            execution_verified=False,
            correlation_id=correlation_id,
        )
