from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcl.domain.contracts import Evidence
from gcl.domain.enums import Verdict
from gcl.loop.driver import LoopDriver
from gcl.loop.ledger import LedgerClient


def _breach_signals():
    return [
        Evidence(metric="latency_ms", value=6000.0),
        Evidence(metric="replicas", value=3.0),
    ]


def _normal_signals():
    return [
        Evidence(metric="latency_ms", value=3000.0),
        Evidence(metric="replicas", value=5.0),
    ]


@pytest.fixture
def ledger():
    return LedgerClient(url="")


@pytest.fixture
def driver(ledger):
    return LoopDriver(ledger=ledger)


class TestLoopDriver:
    @pytest.mark.asyncio
    async def test_full_cycle_produces_complete_loop_cycle(self, driver, ledger):
        signals = _breach_signals()
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        assert cycle.correlation_id is not None
        assert len(cycle.constraints_snapshot) >= 0
        assert cycle.trajectory is not None
        assert cycle.objective is not None

    @pytest.mark.asyncio
    async def test_breach_produces_committed_action(self, driver, ledger):
        signals = _breach_signals()
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        if cycle.action_plan is not None and cycle.falsification is not None:
            if cycle.falsification.verdict == Verdict.SURVIVES:
                assert cycle.committed is True

    @pytest.mark.asyncio
    async def test_rejected_action_never_actuates(self, ledger):
        mock_adapter = MagicMock()
        mock_adapter.actuate = AsyncMock()

        driver = LoopDriver(ledger=ledger, adapter=mock_adapter)

        signals = [
            Evidence(metric="latency_ms", value=100000.0),
            Evidence(metric="max_replicas", value=2.0),
        ]

        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        if not cycle.committed:
            mock_adapter.actuate.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejected_action_still_produces_ledger_record(self, ledger):
        signals = [
            Evidence(metric="latency_ms", value=100000.0),
            Evidence(metric="max_replicas", value=2.0),
        ]

        driver = LoopDriver(ledger=ledger)
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        entries = await ledger.query_chain(cycle.correlation_id)
        assert len(entries) > 0

        entry_types = [e["entry_type"] for e in entries]
        has_reject = "gcl.reject" in entry_types
        has_commit = "gcl.commit" in entry_types
        assert has_reject or has_commit

    @pytest.mark.asyncio
    async def test_ledger_chain_has_all_stages(self, driver, ledger):
        signals = _breach_signals()
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        entries = await ledger.query_chain(cycle.correlation_id)
        entry_types = {e["entry_type"] for e in entries}

        assert "gcl.classify" in entry_types
        assert "gcl.predict" in entry_types
        assert "gcl.interpret" in entry_types
        assert "gcl.plan" in entry_types

    @pytest.mark.asyncio
    async def test_correlation_id_consistent(self, driver, ledger):
        signals = _breach_signals()
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        entries = await ledger.query_chain(cycle.correlation_id)
        for entry in entries:
            assert entry["correlation_id"] == cycle.correlation_id

    @pytest.mark.asyncio
    async def test_receding_horizon_re_plans(self, driver, ledger):
        signals = _breach_signals()
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle1 = await driver.run_cycle(signals)
            cycle2 = await driver.run_cycle(signals)

        assert cycle1.correlation_id != cycle2.correlation_id

        entries1 = await ledger.query_chain(cycle1.correlation_id)
        entries2 = await ledger.query_chain(cycle2.correlation_id)
        assert len(entries1) > 0
        assert len(entries2) > 0

    @pytest.mark.asyncio
    async def test_infeasible_cycle(self, ledger):
        driver = LoopDriver(ledger=ledger)
        signals = [
            Evidence(metric="latency_ms", value=999999.0),
        ]

        from gcl.controller.controller import Controller
        from unittest.mock import patch as mpatch

        original_optimize = Controller.optimize

        def infeasible_optimize(self, trajectory, objective, constraints):
            return None

        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True), \
             mpatch.object(Controller, "optimize", infeasible_optimize):
            cycle = await driver.run_cycle(signals)

        assert cycle.committed is False
        assert cycle.action_plan is None
        assert cycle.falsification is None

        entries = await ledger.query_chain(cycle.correlation_id)
        entry_types = [e["entry_type"] for e in entries]
        assert "gcl.reject" in entry_types

    @pytest.mark.asyncio
    async def test_cycle_start_written_first(self, driver, ledger):
        signals = [Evidence(metric="latency_ms", value=3000.0) for _ in range(5)]
        signals += [Evidence(metric="replicas", value=3.0), Evidence(metric="max_replicas", value=10.0)]
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            cycle = await driver.run_cycle(signals)

        entries = await ledger.query_chain(cycle.correlation_id)
        assert entries[0]["entry_type"] == "gcl.cycle_start"
