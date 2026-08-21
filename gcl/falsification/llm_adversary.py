from __future__ import annotations

import json
from typing import Optional, Tuple

from gcl.domain.contracts import ActionStep
from gcl.domain.enums import AdversaryStatus
from gcl.inference.client import infer

_SYSTEM_PROMPT = (
    "You are a falsification adversary for an infrastructure control system. "
    "Your job is to argue why a proposed action will FAIL. "
    "Look for: incorrect assumptions, missing preconditions, timing issues, "
    "capacity problems, or cascading failures. "
    "If you find a compelling reason the action will fail, respond with JSON: "
    '{"fails": true, "reason": "..."}. '
    "If you cannot find a strong argument against the action, respond with: "
    '{"fails": false}.'
)


class LLMAdversary:
    async def probe(
        self, action_step: ActionStep, context: dict
    ) -> Tuple[Optional[str], AdversaryStatus]:
        """Return (objection, status).

        The status distinguishes "ran and found nothing" from "never ran",
        which a bare None could not express. Callers record it so a SURVIVES
        verdict states which gates actually executed.
        """
        prompt = (
            f"Proposed action: {action_step.action_type}\n"
            f"Parameters: {json.dumps(action_step.parameters)}\n"
            f"Predicted effect: {json.dumps(action_step.predicted_effect)}\n"
            f"Context: {json.dumps(context, default=str)}\n\n"
            "Argue why this action will fail, or confirm it is sound."
        )

        result = await infer(prompt, system=_SYSTEM_PROMPT)
        if result is None:
            # No inference endpoint configured, or rules mode short-circuited
            # the call. Either way the adversary did not examine the action.
            return None, AdversaryStatus.UNAVAILABLE

        try:
            raw = result.text.strip()
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None, AdversaryStatus.UNAVAILABLE
            data = json.loads(raw[start : end + 1])
            if data.get("fails"):
                reason = data.get("reason", "LLM adversary found a flaw.")
                return reason, AdversaryStatus.OBJECTED
        except (json.JSONDecodeError, ValueError):
            return None, AdversaryStatus.UNAVAILABLE

        return None, AdversaryStatus.PROBED
