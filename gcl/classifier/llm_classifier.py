from __future__ import annotations

import json
from typing import Optional

from gcl.domain.contracts import Constraint, Evidence
from gcl.domain.enums import ConstraintSource, ConstraintType
from gcl.inference.client import infer

_SYSTEM_PROMPT = (
    "You are a constraint classifier for an infrastructure control system. "
    "Given evidence observations, determine if any constraints apply. "
    "Respond with a JSON array of objects, each with: "
    '"type" (one of: capacity, priority, compliance, residency, budget, latency, custom), '
    '"bound" (numeric threshold), '
    '"hard" (boolean). '
    "If no constraints apply, respond with an empty array []."
)

_MAX_LLM_CONFIDENCE = 0.7


class LLMClassifier:
    async def classify_ambiguous(self, evidence: list[Evidence]) -> list[Constraint]:
        if not evidence:
            return []

        prompt = "Classify these observations into constraints:\n"
        for e in evidence:
            prompt += f"- {e.metric} = {e.value} (source: {e.source})\n"

        result = await infer(prompt, system=_SYSTEM_PROMPT)
        if result is None:
            return []

        return self._parse_response(result.text, evidence)

    def _parse_response(
        self, text: str, evidence: list[Evidence]
    ) -> list[Constraint]:
        try:
            raw = text.strip()
            start = raw.find("[")
            end = raw.rfind("]")
            if start == -1 or end == -1:
                return []
            items = json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return []

        constraints: list[Constraint] = []
        evidence_ids = [e.id for e in evidence]

        for item in items:
            try:
                ctype = ConstraintType(item["type"])
                constraints.append(
                    Constraint(
                        type=ctype,
                        bound=float(item["bound"]),
                        hard=bool(item.get("hard", False)),
                        justification_evidence_ids=evidence_ids,
                        confidence=min(
                            float(item.get("confidence", _MAX_LLM_CONFIDENCE)),
                            _MAX_LLM_CONFIDENCE,
                        ),
                        source=ConstraintSource.LLM,
                    )
                )
            except (KeyError, ValueError):
                continue

        return constraints
