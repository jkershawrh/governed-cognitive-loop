from __future__ import annotations

import inspect
from typing import Optional

from gcl.domain.contracts import ActionStep, FalsificationResult
from gcl.domain.decision_package import SignedDecisionPackageV1
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
        decision_package: Optional[SignedDecisionPackageV1] = None,
    ) -> dict:
        if falsification.verdict == Verdict.SURVIVES:
            if decision_package is None:
                await ledger.write_entry(
                    "gcl.reject",
                    {
                        "action_type": action_step.action_type,
                        "reason": "signed decision package was not produced",
                        "execution_verified": False,
                    },
                    correlation_id,
                )
                return {
                    "committed": False,
                    "fleet_response": None,
                    "proposal_response": None,
                    "decision_package_digest": None,
                }

            proposal_response = {
                "status": "not_configured",
                "reason": "proposer adapter is not configured",
                "package_id": str(decision_package.package.package_id),
                "package_digest": decision_package.digest,
                "execution_verified": False,
            }
            propose = getattr(adapter, "propose", None) if adapter is not None else None
            if propose is not None and callable(propose):
                result = propose(decision_package)
                if inspect.isawaitable(result):
                    result = await result
                if hasattr(result, "model_dump"):
                    proposal_response = result.model_dump(mode="json")
                elif isinstance(result, dict):
                    proposal_response = dict(result)
                proposal_response["execution_verified"] = False

            proposal_status = proposal_response.get("status", "deferred")
            entry_type = {
                "accepted": "gcl.decision_package.proposed",
                "rejected": "gcl.decision_package.proposal_rejected",
            }.get(proposal_status, "gcl.decision_package.proposal_pending")
            await ledger.write_entry(
                entry_type,
                {
                    "action_type": action_step.action_type,
                    "falsification_verdict": falsification.verdict.value,
                    "decision_package_digest": decision_package.digest,
                    "decision_package_id": str(decision_package.package.package_id),
                    "proposal_status": proposal_status,
                    "execution_verified": False,
                },
                correlation_id,
            )
            return {
                "committed": True,
                "fleet_response": proposal_response,
                "proposal_response": proposal_response,
                "decision_package_digest": decision_package.digest,
            }
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
            return {
                "committed": False,
                "fleet_response": None,
                "proposal_response": None,
                "decision_package_digest": None,
            }
