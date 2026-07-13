from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional
from uuid import uuid4

import httpx

from gcl.config import get_settings

logger = logging.getLogger(__name__)


class LedgerClient:
    def __init__(self, url: Optional[str] = None):
        settings = get_settings()
        self._url = (url or settings.ledger_url).rstrip("/")
        self._token = settings.ledger_bearer_token
        self._timeout = settings.ledger_timeout_seconds
        self._memory: list[dict] = []

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    async def write_entry(
        self, entry_type: str, content: dict, correlation_id: str
    ) -> str:
        entry_id = str(uuid4())
        content_json = json.dumps(
            content,
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        )
        input_hash = hashlib.sha256(content_json.encode("utf-8")).hexdigest()
        idempotency_key = hashlib.sha256(
            f"{entry_type}\0{correlation_id}\0{input_hash}".encode("utf-8")
        ).hexdigest()

        mem_entry = {
            "entry_id": entry_id,
            "entry_type": entry_type,
            "agent_id": "governed-cognitive-loop",
            "content": content,
            "content_type": "application/json",
            "source_id": "gcl",
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "input_hash": input_hash,
            "proof": {
                "external": False,
                "provider": "are-immutable-ledger",
            },
        }

        if not self._url:
            self._memory.append(mem_entry)
            return entry_id

        wire_entry = {
            "entry_type": entry_type,
            "agent_id": mem_entry["agent_id"],
            "content": content_json,
            "content_type": mem_entry["content_type"],
            "source_id": mem_entry["source_id"],
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "input_hash": input_hash,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._url}/api/receipts",
                    json=wire_entry,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
                remote_entry_id = str(data.get("entry_id", entry_id))
                mem_entry["entry_id"] = remote_entry_id
                mem_entry["proof"] = {
                    "external": True,
                    "provider": "are-immutable-ledger",
                    "entry_hash": data.get("entry_hash", ""),
                    "chain_position": data.get("chain_position"),
                    "written_ts": data.get("written_ts"),
                    "input_hash": data.get("input_hash", input_hash),
                }
                self._memory.append(mem_entry)
                return remote_entry_id
        except Exception as e:
            logger.warning(
                "Immutable-ledger proof write failed, retaining local evidence only: %s",
                e,
            )
            self._memory.append(mem_entry)
            return entry_id

    async def query_chain(self, correlation_id: str) -> list[dict]:
        if not self._url:
            return [e for e in self._memory if e["correlation_id"] == correlation_id]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._url}/api/receipts/chain",
                    params={"correlation_id": correlation_id},
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "entries" in data:
                    return data["entries"]
                return data
        except Exception as e:
            logger.warning("Ledger proof query failed, returning local evidence: %s", e)
            return [e for e in self._memory if e["correlation_id"] == correlation_id]

    async def verify_proof(self, entry_hash: str, entry_type: str) -> dict:
        """Verify an external proof receipt; never interpret it as authority."""
        if not self._url:
            return {
                "valid": False,
                "failure_reason": "are-immutable-ledger endpoint is not configured",
            }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._url}/api/receipts/verify",
                    params={"hash": entry_hash, "type": entry_type},
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:
            logger.warning("Ledger proof verification failed: %s", exc)
        return {"valid": False, "failure_reason": "proof verification unavailable"}

    def get_memory_entries(self) -> list[dict]:
        return list(self._memory)
