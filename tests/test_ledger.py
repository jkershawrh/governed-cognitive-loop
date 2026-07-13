from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcl.loop.ledger import LedgerClient


@pytest.fixture
def ledger():
    return LedgerClient(url="")


class TestLedgerClient:
    @pytest.mark.asyncio
    async def test_write_and_query(self, ledger):
        corr_id = "test-001"
        entry_id = await ledger.write_entry("gcl.classify", {"test": True}, corr_id)
        assert entry_id is not None

        entries = await ledger.query_chain(corr_id)
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "gcl.classify"
        assert entries[0]["correlation_id"] == corr_id

    @pytest.mark.asyncio
    async def test_multiple_entries_same_chain(self, ledger):
        corr_id = "test-002"
        await ledger.write_entry("gcl.classify", {}, corr_id)
        await ledger.write_entry("gcl.predict", {}, corr_id)
        await ledger.write_entry("gcl.interpret", {}, corr_id)

        entries = await ledger.query_chain(corr_id)
        assert len(entries) == 3
        types = [e["entry_type"] for e in entries]
        assert "gcl.classify" in types
        assert "gcl.predict" in types
        assert "gcl.interpret" in types

    @pytest.mark.asyncio
    async def test_separate_correlation_ids(self, ledger):
        await ledger.write_entry("gcl.classify", {}, "chain-a")
        await ledger.write_entry("gcl.classify", {}, "chain-b")

        entries_a = await ledger.query_chain("chain-a")
        entries_b = await ledger.query_chain("chain-b")
        assert len(entries_a) == 1
        assert len(entries_b) == 1

    @pytest.mark.asyncio
    async def test_query_empty_chain(self, ledger):
        entries = await ledger.query_chain("nonexistent")
        assert entries == []

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_url(self):
        ledger = LedgerClient(url="")
        entry_id = await ledger.write_entry("gcl.test", {"data": 1}, "corr-1")
        assert entry_id is not None

        entries = ledger.get_memory_entries()
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_entry_has_agent_id(self, ledger):
        await ledger.write_entry("gcl.classify", {}, "corr-2")
        entries = ledger.get_memory_entries()
        assert entries[0]["agent_id"] == "governed-cognitive-loop"
        assert entries[0]["source_id"] == "gcl"

    @pytest.mark.asyncio
    async def test_external_write_uses_real_proof_receipt_api(self, monkeypatch):
        monkeypatch.setenv("GCL_LEDGER_BEARER_TOKEN", "ledger-token")
        from gcl.config import get_settings

        get_settings.cache_clear()
        response = MagicMock()
        response.json.return_value = {
            "entry_id": "entry-1",
            "entry_hash": "hash-1",
            "chain_position": 7,
            "written_ts": 123,
        }
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)

        with patch("gcl.loop.ledger.httpx.AsyncClient", return_value=client):
            ledger = LedgerClient(url="https://ledger.example.test")
            entry_id = await ledger.write_entry(
                "gcl.decision_package.proposed",
                {"digest": "sha256:abc"},
                "corr-proof",
            )

        assert entry_id == "entry-1"
        call = client.post.await_args
        assert call.args[0] == "https://ledger.example.test/api/receipts"
        assert call.kwargs["headers"]["Authorization"] == "Bearer ledger-token"
        assert len(call.kwargs["json"]["input_hash"]) == 64
        assert len(call.kwargs["json"]["idempotency_key"]) == 64
        assert ledger.get_memory_entries()[0]["proof"]["external"] is True

    @pytest.mark.asyncio
    async def test_receipt_verification_uses_real_verify_endpoint(self):
        response = MagicMock()
        response.json.return_value = {"valid": True, "entry_type": "gcl.plan"}
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=response)

        with patch("gcl.loop.ledger.httpx.AsyncClient", return_value=client):
            result = await LedgerClient(url="https://ledger.example.test").verify_proof(
                "hash-1", "gcl.plan"
            )

        assert result["valid"] is True
        call = client.get.await_args
        assert call.args[0] == "https://ledger.example.test/api/receipts/verify"
        assert call.kwargs["params"] == {"hash": "hash-1", "type": "gcl.plan"}
