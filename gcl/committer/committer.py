from __future__ import annotations

from typing import Optional

from gcl.domain.contracts import ActionStep, FalsificationResult
from gcl.domain.enums import Verdict
from gcl.loop.ledger import LedgerClient


class Committer:
    async def commit(
        self,
        action_step: ActionStep,
        falsification: FalsificationResult,
        adapter: Optional[object],
        ledger: LedgerClient,
        correlation_id: str,
    ) -> dict:
        if falsification.verdict == Verdict.SURVIVES:
            adapter_result = None
            if adapter is not None and hasattr(adapter, "actuate"):
                adapter_result = await adapter.actuate(action_step, correlation_id)

            await ledger.write_entry(
                "gcl.commit",
                {
                    "action_type": action_step.action_type,
                    "parameters": action_step.parameters,
                    "falsification_verdict": falsification.verdict.value,
                },
                correlation_id,
            )
            return {"committed": True, "fleet_response": adapter_result}
        else:
            await ledger.write_entry(
                "gcl.reject",
                {
                    "action_type": action_step.action_type,
                    "parameters": action_step.parameters,
                    "falsification_verdict": falsification.verdict.value,
                    "failed_check": falsification.failed_check,
                    "reasoning": falsification.reasoning,
                },
                correlation_id,
            )
            return {"committed": False, "fleet_response": None}
