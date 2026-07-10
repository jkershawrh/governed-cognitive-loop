from __future__ import annotations

from gcl.domain.contracts import Constraint, Evidence
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

        llm_constraints: list[Constraint] = []
        if unmatched and not get_force_rules():
            llm_constraints = await self._llm.classify_ambiguous(unmatched)

        all_constraints = deterministic + llm_constraints

        return [c for c in all_constraints if c.justification_evidence_ids]
