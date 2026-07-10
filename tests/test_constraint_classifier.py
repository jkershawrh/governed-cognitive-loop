from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from gcl.classifier.classifier import ConstraintClassifier
from gcl.classifier.llm_classifier import LLMClassifier
from gcl.classifier.rules import RuleEngine
from gcl.domain.contracts import Constraint, Evidence
from gcl.domain.enums import ConstraintSource, ConstraintType
from gcl.inference.client import InferenceResult


def _make_rules():
    return [
        {
            "name": "latency_breach",
            "metric": "latency_ms",
            "operator": "gt",
            "threshold": 5000,
            "constraint_type": "latency",
            "hard": True,
            "confidence": 0.9,
        },
        {
            "name": "budget_limit",
            "metric": "hourly_cost",
            "operator": "gt",
            "threshold": 1000,
            "constraint_type": "budget",
            "hard": False,
            "confidence": 0.85,
        },
    ]


@pytest.fixture
def rule_engine():
    return RuleEngine(rules=_make_rules())


@pytest.fixture
def classifier(rule_engine):
    return ConstraintClassifier(rule_engine=rule_engine)


class TestRuleEngine:
    def test_clear_evidence_produces_constraint(self, rule_engine):
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        constraints, unmatched = rule_engine.evaluate(evidence)
        assert len(constraints) == 1
        assert constraints[0].type == ConstraintType.LATENCY
        assert constraints[0].hard is True
        assert constraints[0].source == ConstraintSource.DETERMINISTIC
        assert constraints[0].confidence == 0.9
        assert evidence[0].id in constraints[0].justification_evidence_ids

    def test_below_threshold_no_constraint(self, rule_engine):
        evidence = [Evidence(metric="latency_ms", value=3000.0)]
        constraints, unmatched = rule_engine.evaluate(evidence)
        assert len(constraints) == 0
        assert len(unmatched) == 1

    def test_unknown_metric_unmatched(self, rule_engine):
        evidence = [Evidence(metric="unknown_metric", value=999.0)]
        constraints, unmatched = rule_engine.evaluate(evidence)
        assert len(constraints) == 0
        assert len(unmatched) == 1

    def test_multiple_rules_match(self, rule_engine):
        evidence = [
            Evidence(metric="latency_ms", value=6000.0),
            Evidence(metric="hourly_cost", value=1500.0),
        ]
        constraints, unmatched = rule_engine.evaluate(evidence)
        assert len(constraints) == 2
        types = {c.type for c in constraints}
        assert ConstraintType.LATENCY in types
        assert ConstraintType.BUDGET in types


class TestConstraintClassifier:
    @pytest.mark.asyncio
    async def test_clear_evidence_deterministic(self, classifier):
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        constraints = await classifier.classify(evidence)
        assert len(constraints) == 1
        assert constraints[0].source == ConstraintSource.DETERMINISTIC

    @pytest.mark.asyncio
    async def test_empty_evidence_returns_empty(self, classifier):
        constraints = await classifier.classify([])
        assert constraints == []

    @pytest.mark.asyncio
    async def test_ambiguous_evidence_falls_to_llm(self, classifier):
        evidence = [Evidence(metric="custom_signal", value=42.0)]

        llm_response = InferenceResult(
            text='[{"type": "custom", "bound": 50.0, "hard": false}]',
            model="test",
        )
        with patch("gcl.classifier.classifier.get_force_rules", return_value=False), \
             patch("gcl.classifier.llm_classifier.infer", new_callable=AsyncMock, return_value=llm_response):
            constraints = await classifier.classify(evidence)

        assert len(constraints) == 1
        assert constraints[0].source == ConstraintSource.LLM

    @pytest.mark.asyncio
    async def test_llm_constraints_marked_lower_confidence(self, classifier):
        evidence = [Evidence(metric="custom_signal", value=42.0)]

        llm_response = InferenceResult(
            text='[{"type": "custom", "bound": 50.0, "hard": false, "confidence": 0.99}]',
            model="test",
        )
        with patch("gcl.classifier.classifier.get_force_rules", return_value=False), \
             patch("gcl.classifier.llm_classifier.infer", new_callable=AsyncMock, return_value=llm_response):
            constraints = await classifier.classify(evidence)

        assert len(constraints) == 1
        assert constraints[0].confidence <= 0.7

    @pytest.mark.asyncio
    async def test_deterministic_fallback_when_llm_unavailable(self, classifier):
        evidence = [
            Evidence(metric="latency_ms", value=6000.0),
            Evidence(metric="custom_signal", value=42.0),
        ]

        with patch("gcl.classifier.llm_classifier.infer", new_callable=AsyncMock, return_value=None):
            constraints = await classifier.classify(evidence)

        assert len(constraints) == 1
        assert constraints[0].source == ConstraintSource.DETERMINISTIC

    @pytest.mark.asyncio
    async def test_constraint_without_evidence_dropped(self, classifier):
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        constraints = await classifier.classify(evidence)
        for c in constraints:
            assert len(c.justification_evidence_ids) > 0

    @pytest.mark.asyncio
    async def test_conflicting_evidence(self, classifier):
        evidence = [
            Evidence(metric="latency_ms", value=6000.0),
            Evidence(metric="latency_ms", value=3000.0),
        ]
        constraints = await classifier.classify(evidence)
        assert len(constraints) == 1
        assert constraints[0].type == ConstraintType.LATENCY

    @pytest.mark.asyncio
    async def test_force_rules_skips_llm(self, classifier):
        evidence = [Evidence(metric="custom_signal", value=42.0)]

        with patch("gcl.classifier.classifier.get_force_rules", return_value=True):
            constraints = await classifier.classify(evidence)

        assert len(constraints) == 0
