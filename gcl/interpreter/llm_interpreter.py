from __future__ import annotations

import json
from typing import Optional

from gcl.domain.contracts import Constraint, ObjectiveSpec
from gcl.inference.client import infer

_SYSTEM_PROMPT = (
    "You are an objective interpreter for an infrastructure control system. "
    "Given context and constraints, produce an ObjectiveSpec as JSON with: "
    '"terms" (list of cost term names), '
    '"weights" (list of floats summing to 1.0), '
    '"rationale" (one sentence explaining the weighting). '
    "You must NEVER produce an action, action plan, or control command. "
    "You only specify what to optimize for, not how to achieve it."
)


class LLMInterpreter:
    async def interpret(
        self, context: dict, constraints: list[Constraint]
    ) -> Optional[ObjectiveSpec]:
        constraint_desc = []
        hard_ids = []
        soft_ids = []
        for c in constraints:
            constraint_desc.append(
                f"- {c.type.value}: bound={c.bound}, hard={c.hard}, confidence={c.confidence}"
            )
            if c.hard:
                hard_ids.append(c.id)
            else:
                soft_ids.append(c.id)

        prompt = (
            "Context:\n"
            + json.dumps(context, default=str)
            + "\n\nActive constraints:\n"
            + "\n".join(constraint_desc)
            + "\n\nProduce an ObjectiveSpec JSON."
        )

        result = await infer(prompt, system=_SYSTEM_PROMPT)
        if result is None:
            return None

        return self._parse_response(result.text, hard_ids, soft_ids)

    def _parse_response(self, text: str, hard_ids: list, soft_ids: list) -> Optional[ObjectiveSpec]:
        try:
            raw = text.strip()
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None
            data = json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None

        try:
            return ObjectiveSpec(
                terms=data["terms"],
                weights=data["weights"],
                hard_constraint_ids=hard_ids,
                soft_constraint_ids=soft_ids,
                rationale=data.get("rationale", "LLM-generated objective."),
            )
        except (KeyError, ValueError):
            return None
