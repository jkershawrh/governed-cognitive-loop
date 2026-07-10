from __future__ import annotations

from gcl.domain.contracts import Constraint, ObjectiveSpec
from gcl.inference.client import get_force_rules
from gcl.interpreter.llm_interpreter import LLMInterpreter
from gcl.interpreter.templates import TemplateInterpreter


class ObjectiveInterpreter:
    def __init__(self):
        self._template = TemplateInterpreter()
        self._llm = LLMInterpreter()

    async def interpret(
        self, context: dict, constraints: list[Constraint]
    ) -> ObjectiveSpec:
        if not get_force_rules():
            result = await self._llm.interpret(context, constraints)
            if result is not None:
                return result

        return self._template.interpret(constraints)
