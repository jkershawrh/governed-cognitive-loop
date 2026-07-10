from __future__ import annotations

from gcl.domain.contracts import Constraint, Evidence
from gcl.domain.enums import ConstraintSource, ConstraintType
from gcl.classifier.rules import RuleEngine
from gcl.classifier.llm_classifier import LLMClassifier
from gcl.inference.client import get_force_rules


class ConstraintClassifier:
    def __init__(self, rule_engine: RuleEngine | None = None, llm_classifier: LLMClassifier | None = None):
        self._rules = rule_engine or RuleEngine()
        self._llm = llm_classifier or LLMClassifier()

    async def classify(self, evidence: list[Evidence]) -> list[Constraint]:
        if not evidence:
            return []

        deterministic, unmatched = self._rules.evaluate(evidence)

        capacity_constraints = self._derive_capacity_from_evidence(evidence)
        deterministic.extend(capacity_constraints)

        llm_constraints: list[Constraint] = []
        if unmatched and not get_force_rules():
            llm_constraints = await self._llm.classify_ambiguous(unmatched)

        all_constraints = deterministic + llm_constraints

        return [c for c in all_constraints if c.justification_evidence_ids]

    def _derive_capacity_from_evidence(self, evidence: list[Evidence]) -> list[Constraint]:
        """Create capacity constraints from max_replicas evidence."""
        constraints: list[Constraint] = []
        for e in evidence:
            if e.metric == "max_replicas":
                constraints.append(Constraint(
                    type=ConstraintType.CAPACITY,
                    bound=e.value,
                    hard=True,
                    justification_evidence_ids=[e.id],
                    confidence=0.95,
                    source=ConstraintSource.DETERMINISTIC,
                ))
        return constraints
