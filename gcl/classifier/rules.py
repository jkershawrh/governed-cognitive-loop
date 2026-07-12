from __future__ import annotations

import datetime
import operator
from typing import Optional
from uuid import uuid4

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

            # Time-based rules
            if op_name == "time_between":
                current_hour = datetime.datetime.now().hour
                start = rule.get("start_hour", 0)
                end = rule.get("end_hour", 0)
                in_window = (start <= current_hour < end) if start < end else (current_hour >= start or current_hour < end)
                if in_window:
                    constraints.append(Constraint(
                        type=ConstraintType(rule.get("constraint_type", "custom")),
                        bound=float(rule.get("threshold", 0)),
                        hard=rule.get("hard", True),
                        justification_evidence_ids=[uuid4()],
                        confidence=rule.get("confidence", 1.0),
                        source=ConstraintSource.DETERMINISTIC,
                    ))
                continue

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
