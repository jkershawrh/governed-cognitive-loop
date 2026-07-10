from __future__ import annotations

import ast
import inspect
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from gcl.domain.contracts import Constraint, ObjectiveSpec
from gcl.domain.enums import ConstraintSource, ConstraintType
from gcl.inference.client import InferenceResult
from gcl.interpreter.interpreter import ObjectiveInterpreter
from gcl.interpreter.templates import TemplateInterpreter
from tests.conftest import make_constraint


def _make_latency_constraints():
    return [
        make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True),
    ]


def _make_mixed_constraints():
    return [
        make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True),
        make_constraint(ctype=ConstraintType.BUDGET, bound=1000.0, hard=False),
        make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True),
    ]


class TestHonestyBoundary:
    def test_llm_boundary_no_action_path(self):
        """The interpreter module must never import or return ActionPlan or ActionStep."""
        interpreter_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "gcl", "interpreter"
        )
        forbidden = {"ActionPlan", "ActionStep"}

        for filename in os.listdir(interpreter_dir):
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(interpreter_dir, filename)
            with open(filepath) as f:
                source = f.read()

            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        assert name not in forbidden, (
                            f"{filename} imports {name}, violating the honesty boundary"
                        )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        assert name not in forbidden

    def test_interpreter_return_type_is_objective_spec(self):
        """ObjectiveInterpreter.interpret returns ObjectiveSpec, not an action type."""
        hints = ObjectiveInterpreter.interpret.__annotations__
        ret = hints.get("return")
        assert ret is ObjectiveSpec or ret == "ObjectiveSpec", (
            f"interpret() return annotation is {ret}, expected ObjectiveSpec"
        )


class TestTemplateInterpreter:
    def test_template_fallback_produces_valid_objective(self):
        interp = TemplateInterpreter()
        constraints = _make_latency_constraints()
        result = interp.interpret(constraints)
        assert isinstance(result, ObjectiveSpec)
        assert len(result.terms) > 0
        assert len(result.weights) == len(result.terms)
        assert result.rationale

    def test_latency_constraint_selects_latency_template(self):
        interp = TemplateInterpreter()
        constraints = _make_latency_constraints()
        result = interp.interpret(constraints)
        assert "latency_cost" in result.terms

    def test_compliance_constraint_dominates(self):
        interp = TemplateInterpreter()
        constraints = [
            make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True),
            make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True),
        ]
        result = interp.interpret(constraints)
        assert "compliance_cost" in result.terms

    def test_constraint_partition(self):
        interp = TemplateInterpreter()
        constraints = _make_mixed_constraints()
        result = interp.interpret(constraints)
        hard = [c for c in constraints if c.hard]
        soft = [c for c in constraints if not c.hard]
        assert len(result.hard_constraint_ids) == len(hard)
        assert len(result.soft_constraint_ids) == len(soft)

    def test_empty_constraints_uses_balanced(self):
        interp = TemplateInterpreter()
        result = interp.interpret([])
        assert len(result.terms) > 0


class TestObjectiveInterpreter:
    @pytest.mark.asyncio
    async def test_deterministic_fallback(self):
        interp = ObjectiveInterpreter()
        constraints = _make_latency_constraints()
        with patch("gcl.interpreter.interpreter.get_force_rules", return_value=True):
            result = await interp.interpret({}, constraints)
        assert isinstance(result, ObjectiveSpec)
        assert len(result.terms) > 0

    @pytest.mark.asyncio
    async def test_llm_produces_valid_objective(self):
        interp = ObjectiveInterpreter()
        constraints = _make_latency_constraints()

        llm_response = InferenceResult(
            text='{"terms": ["latency_cost", "throughput_cost"], "weights": [0.7, 0.3], "rationale": "Latency is primary."}',
            model="test",
        )
        with patch("gcl.interpreter.interpreter.get_force_rules", return_value=False):
            with patch("gcl.interpreter.llm_interpreter.infer", new_callable=AsyncMock, return_value=llm_response):
                result = await interp.interpret({}, constraints)

        assert isinstance(result, ObjectiveSpec)
        assert result.terms == ["latency_cost", "throughput_cost"]

    @pytest.mark.asyncio
    async def test_llm_unavailable_falls_to_template(self):
        interp = ObjectiveInterpreter()
        constraints = _make_latency_constraints()

        with patch("gcl.interpreter.interpreter.get_force_rules", return_value=False):
            with patch("gcl.interpreter.llm_interpreter.infer", new_callable=AsyncMock, return_value=None):
                result = await interp.interpret({}, constraints)

        assert isinstance(result, ObjectiveSpec)
        assert "latency_cost" in result.terms

    def test_no_optimality_claim_in_templates(self):
        interp = TemplateInterpreter()
        for constraints in [
            _make_latency_constraints(),
            _make_mixed_constraints(),
            [],
        ]:
            result = interp.interpret(constraints)
            lower = result.rationale.lower()
            assert "optimal" not in lower, f"Rationale claims optimality: {result.rationale}"
