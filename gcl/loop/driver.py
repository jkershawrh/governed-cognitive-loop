from __future__ import annotations

from typing import Optional
from uuid import uuid4

from gcl.classifier.classifier import ConstraintClassifier
from gcl.committer.committer import Committer
from gcl.config import get_settings
from gcl.controller.controller import Controller
from gcl.domain.contracts import Evidence, LoopCycle
from gcl.falsification.gate import FalsificationGate
from gcl.interpreter.interpreter import ObjectiveInterpreter
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
    ):
        self._classifier = classifier or ConstraintClassifier()
        self._predictor = predictor or HorizonPredictor()
        self._interpreter = interpreter or ObjectiveInterpreter()
        self._controller = controller or Controller()
        self._gate = gate or FalsificationGate()
        self._committer = committer or Committer()
        self._ledger = ledger or LedgerClient()
        self._adapter = adapter

    async def run_cycle(self, signals: list[Evidence]) -> LoopCycle:
        settings = get_settings()
        correlation_id = f"gcl-{uuid4()}"

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
        falsification = await self._gate.falsify(
            committed_step, trajectory, constraints, signals,
        )
        await self._ledger.write_entry(
            "gcl.falsify",
            falsification.model_dump(mode="json"),
            correlation_id,
        )

        did_commit = await self._committer.commit(
            committed_step, falsification, self._adapter, self._ledger, correlation_id,
        )

        return LoopCycle(
            constraints_snapshot=constraints,
            trajectory=trajectory,
            objective=objective,
            action_plan=action_plan,
            falsification=falsification,
            committed=did_commit,
            correlation_id=correlation_id,
        )
