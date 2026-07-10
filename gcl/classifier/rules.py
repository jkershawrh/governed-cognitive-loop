from __future__ import annotations

import operator
from typing import Optional

from gcl.config import get_constraint_rules
from gcl.domain.contracts import Constraint, Evidence
from gcl.domain.enums import ConstraintSource, ConstraintType

_OPS = {
    "gt": operator.gt,
    "lt": operator.lt,
    "gte": operator.ge,
    "lte": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
}


class RuleEngine:
    def __init__(self, rules: Optional[list] = None):
        self._rules = rules if rules is not None else get_constraint_rules()

    def evaluate(self, evidence: list[Evidence]) -> tuple[list[Constraint], list[Evidence]]:
        constraints: list[Constraint] = []
        matched_evidence_ids = set()

        evidence_by_metric: dict[str, list[Evidence]] = {}
        for e in evidence:
            evidence_by_metric.setdefault(e.metric, []).append(e)

        for rule in self._rules:
            metric = rule["metric"]
            op_name = rule["operator"]
            threshold = rule.get("threshold")
            ctype_str = rule["constraint_type"]
            hard = rule.get("hard", True)
            confidence = rule.get("confidence", 0.9)

            op_fn = _OPS.get(op_name)
            if op_fn is None:
                continue

            matching = evidence_by_metric.get(metric, [])
            for e in matching:
                if threshold is not None and op_fn(e.value, threshold):
                    constraints.append(
                        Constraint(
                            type=ConstraintType(ctype_str),
                            bound=threshold,
                            hard=hard,
                            justification_evidence_ids=[e.id],
                            confidence=confidence,
                            source=ConstraintSource.DETERMINISTIC,
                        )
                    )
                    matched_evidence_ids.add(e.id)

        unmatched = [e for e in evidence if e.id not in matched_evidence_ids]
        return constraints, unmatched
