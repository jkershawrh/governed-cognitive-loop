from __future__ import annotations

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
