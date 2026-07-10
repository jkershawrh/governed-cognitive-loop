from __future__ import annotations

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
        self._url = url or settings.ledger_url
        self._timeout = settings.ledger_timeout_seconds
        self._memory: list[dict] = []

    async def write_entry(
        self, entry_type: str, content: dict, correlation_id: str
    ) -> str:
        entry_id = str(uuid4())

        mem_entry = {
            "entry_id": entry_id,
            "entry_type": entry_type,
            "agent_id": "governed-cognitive-loop",
            "content": content,
            "content_type": "application/json",
            "source_id": "gcl",
            "correlation_id": correlation_id,
        }

        if not self._url:
            self._memory.append(mem_entry)
            return entry_id

        wire_entry = dict(mem_entry)
        wire_entry["content"] = json.dumps(content, default=str)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._url}/api/entries",
                    json=wire_entry,
                )
                response.raise_for_status()
                data = response.json()
                self._memory.append(mem_entry)
                return data.get("entry_id", entry_id)
        except (httpx.HTTPError, Exception) as e:
            logger.warning("Ledger write failed, storing in memory only: %s", e)
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
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "entries" in data:
                    return data["entries"]
                return data
        except (httpx.HTTPError, Exception) as e:
            logger.warning("Ledger query failed, returning from memory: %s", e)
            return [e for e in self._memory if e["correlation_id"] == correlation_id]

    def get_memory_entries(self) -> list[dict]:
        return list(self._memory)
