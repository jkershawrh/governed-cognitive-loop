from __future__ import annotations

from gcl.config import get_objective_templates
from gcl.domain.contracts import Constraint, ObjectiveSpec
from gcl.domain.enums import ConstraintType


class TemplateInterpreter:
    def __init__(self):
        self._templates = get_objective_templates()

    def interpret(self, constraints: list[Constraint]) -> ObjectiveSpec:
        constraint_types = {c.type for c in constraints}
        hard_ids = [c.id for c in constraints if c.hard]
        soft_ids = [c.id for c in constraints if not c.hard]

        template = self._select_template(constraint_types)

        return ObjectiveSpec(
            terms=template["terms"],
            weights=template["weights"],
            hard_constraint_ids=hard_ids,
            soft_constraint_ids=soft_ids,
            rationale=template["rationale"],
        )

    def _select_template(self, constraint_types: set[ConstraintType]) -> dict:
        if ConstraintType.COMPLIANCE in constraint_types:
            return self._templates.get("compliance_override", self._balanced())

        if ConstraintType.CAPACITY in constraint_types and ConstraintType.LATENCY in constraint_types:
            return self._templates.get("shed_load_focused", self._balanced())

        if ConstraintType.LATENCY in constraint_types:
            return self._templates.get("latency_focused", self._balanced())

        if ConstraintType.CAPACITY in constraint_types:
            return self._templates.get("capacity_focused", self._balanced())

        return self._balanced()

    def _balanced(self) -> dict:
        stored = self._templates.get("balanced")
        if stored:
            return stored
        return {
            "terms": ["latency_cost", "capacity_cost", "resource_cost"],
            "weights": [0.4, 0.3, 0.3],
            "rationale": "Deterministic template: balanced cost weighting.",
        }
