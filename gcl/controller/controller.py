from __future__ import annotations

from typing import Optional

from gcl.domain.contracts import (
    ActionPlan,
    ActionStep,
    Constraint,
    ObjectiveSpec,
    Trajectory,
)
from gcl.controller.optimizer import (
    check_hard_constraint_satisfaction,
    compute_action_for_step,
)


class Controller:
    """Deterministic controller. Does not claim optimality.
    Guarantees: hard-constraint satisfaction and receding-horizon discipline."""

    def optimize(
        self,
        trajectory: Trajectory,
        objective: ObjectiveSpec,
        constraints: list[Constraint],
    ) -> Optional[ActionPlan]:
        hard = [c for c in constraints if c.hard]
        soft = [c for c in constraints if not c.hard]

        weights = dict(zip(objective.terms, objective.weights))

        steps: list[ActionStep] = []
        for i, point in enumerate(trajectory.points):
            result = compute_action_for_step(point, hard, soft, weights)
            if result is None and i == 0:
                return None

            if result is None:
                result = {"action_type": "no_action", "parameters": {}}

            action_params = result
            if not check_hard_constraint_satisfaction(action_params, hard):
                if i == 0:
                    return None
                action_params = {"action_type": "no_action", "parameters": {}}

            steps.append(
                ActionStep(
                    step_index=i,
                    action_type=action_params["action_type"],
                    parameters=action_params["parameters"],
                )
            )

        if not steps:
            return None

        return ActionPlan(
            steps=steps,
            committed_step_index=0,
            horizon_steps=trajectory.horizon_steps,
        )
