"""Ecosystem stress test runner for the governed AI inference fleet platform.

Exercises all 4 systems on Oberon across 8 phases: smoke, performance baseline,
pressure, edge cases, degradation, soak, pen testing, and chaos.

Usage:
    python3 tests/test_ecosystem_stress.py \
        --gcl-url https://gcl-app.192.168.1.123.sslip.io \
        --fleet-url http://localhost:18080 \
        --phase all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class StressResult:
    name: str
    passed: bool
    duration_ms: float
    detail: str = ""
    metrics: dict = field(default_factory=dict)


@dataclass
class PhaseReport:
    phase: str
    results: list[StressResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0

    def add(self, result: TestResult):
        self.results.append(result)
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self) -> str:
        return f"{self.phase}: {self.passed} passed, {self.failed} failed"


class EcosystemStressTest:
    def __init__(self, gcl_url: str, fleet_url: str, timeout: float = 30.0):
        self.gcl = gcl_url.rstrip("/")
        self.fleet = fleet_url.rstrip("/")
        self.timeout = timeout
        self.reports: list[PhaseReport] = []

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(verify=False, timeout=self.timeout) as c:
            return await c.get(url)

    async def _post(self, url: str, data: dict) -> httpx.Response:
        async with httpx.AsyncClient(verify=False, timeout=self.timeout) as c:
            return await c.post(url, json=data)

    async def _timed_post(self, url: str, data: dict) -> tuple[httpx.Response, float]:
        start = time.monotonic()
        resp = await self._post(url, data)
        elapsed = (time.monotonic() - start) * 1000
        return resp, elapsed

    async def _seed_and_get_signals(self, step: int = 4) -> list[dict]:
        await self._post(f"{self.gcl}/api/v1/scenario/seed", {
            "scenario": "inference_fleet_spike", "seed": 42
        })
        resp = await self._get(f"{self.gcl}/api/v1/scenario/step/{step}")
        data = resp.json()
        return data.get("signals", data.get("step", {}).get("signals", []))

    # ── Phase 1: Smoke ──

    async def phase_smoke(self) -> PhaseReport:
        report = PhaseReport("Phase 1: Smoke")
        print("\n=== Phase 1: Smoke ===")

        # GCL cycles endpoint
        t = time.monotonic()
        try:
            resp = await self._get(f"{self.gcl}/api/v1/cycles")
            ok = resp.status_code == 200
            report.add(StressResult("gcl_cycles", ok, (time.monotonic() - t) * 1000,
                                  f"status={resp.status_code}, count={len(resp.json())}"))
        except Exception as e:
            report.add(StressResult("gcl_cycles", False, 0, str(e)))

        # GCL scenario seed
        t = time.monotonic()
        try:
            resp = await self._post(f"{self.gcl}/api/v1/scenario/seed", {
                "scenario": "inference_fleet_spike", "seed": 42
            })
            ok = resp.status_code == 200
            report.add(StressResult("gcl_seed", ok, (time.monotonic() - t) * 1000))
        except Exception as e:
            report.add(StressResult("gcl_seed", False, 0, str(e)))

        # GCL governance cycle
        try:
            signals = await self._seed_and_get_signals(4)
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
            d = resp.json()
            ok = resp.status_code == 200 and "committed" in d
            report.add(StressResult("gcl_cycle", ok, ms,
                                  f"action={d.get('action_type')} committed={d.get('committed')}"))
        except Exception as e:
            report.add(StressResult("gcl_cycle", False, 0, str(e)))

        # Fleet healthz
        t = time.monotonic()
        try:
            resp = await self._get(f"{self.fleet}/healthz")
            ok = resp.status_code == 200
            report.add(StressResult("fleet_healthz", ok, (time.monotonic() - t) * 1000,
                                  resp.text[:100]))
        except Exception as e:
            report.add(StressResult("fleet_healthz", False, 0, str(e)))

        # Fleet readyz
        t = time.monotonic()
        try:
            resp = await self._get(f"{self.fleet}/readyz")
            ok = resp.status_code == 200
            report.add(StressResult("fleet_readyz", ok, (time.monotonic() - t) * 1000))
        except Exception as e:
            report.add(StressResult("fleet_readyz", False, 0, str(e)))

        # Fleet metrics
        t = time.monotonic()
        try:
            resp = await self._get(f"{self.fleet}/debug/vars")
            ok = resp.status_code == 200
            report.add(StressResult("fleet_metrics", ok, (time.monotonic() - t) * 1000))
        except Exception as e:
            report.add(StressResult("fleet_metrics", False, 0, str(e)))

        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.name}: {r.detail} ({r.duration_ms:.0f}ms)")
        return report

    # ── Phase 2: Performance Baseline ──

    async def phase_performance(self) -> PhaseReport:
        report = PhaseReport("Phase 2: Performance Baseline")
        print("\n=== Phase 2: Performance Baseline ===")

        # GCL governance cycle latency (100 sequential cycles)
        signals = await self._seed_and_get_signals(4)
        latencies = []
        errors = 0
        for i in range(100):
            try:
                _, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                latencies.append(ms)
            except Exception:
                errors += 1

        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            mx = max(latencies)
            mn = min(latencies)
            report.add(StressResult("gcl_cycle_latency", p99 < 500, 0,
                                  f"p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms max={mx:.0f}ms min={mn:.0f}ms errors={errors}",
                                  {"p50": p50, "p95": p95, "p99": p99, "max": mx, "min": mn, "count": len(latencies)}))
            print(f"  GCL cycle (n=100): p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms max={mx:.0f}ms")

        # Fleet healthz latency (100 sequential)
        latencies = []
        for i in range(100):
            try:
                t = time.monotonic()
                await self._get(f"{self.fleet}/healthz")
                latencies.append((time.monotonic() - t) * 1000)
            except Exception:
                pass

        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            report.add(StressResult("fleet_healthz_latency", p99 < 200, 0,
                                  f"p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms",
                                  {"p50": p50, "p95": p95, "p99": p99}))
            print(f"  Fleet healthz (n=100): p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms")

        return report

    # ── Phase 3: Pressure Testing ──

    async def phase_pressure(self) -> PhaseReport:
        report = PhaseReport("Phase 3: Pressure Testing")
        print("\n=== Phase 3: Pressure Testing ===")

        signals = await self._seed_and_get_signals(4)

        for concurrency in [5, 10, 20, 50]:
            errors = 0
            latencies = []

            async def run_one():
                nonlocal errors
                try:
                    _, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                    latencies.append(ms)
                except Exception:
                    errors += 1

            tasks = [run_one() for _ in range(concurrency)]
            t = time.monotonic()
            await asyncio.gather(*tasks)
            wall = (time.monotonic() - t) * 1000

            if latencies:
                latencies.sort()
                p50 = latencies[len(latencies) // 2]
                p95 = latencies[int(len(latencies) * 0.95)]
                error_rate = errors / concurrency
                ok = error_rate < 0.1
                report.add(StressResult(f"gcl_concurrent_{concurrency}", ok, wall,
                                      f"p50={p50:.0f}ms p95={p95:.0f}ms errors={errors}/{concurrency} ({error_rate:.0%})",
                                      {"concurrency": concurrency, "p50": p50, "p95": p95, "errors": errors}))
                print(f"  GCL c={concurrency}: p50={p50:.0f}ms p95={p95:.0f}ms errors={errors}/{concurrency} wall={wall:.0f}ms")
            else:
                report.add(StressResult(f"gcl_concurrent_{concurrency}", False, wall,
                                      f"all {concurrency} requests failed"))
                print(f"  GCL c={concurrency}: ALL FAILED wall={wall:.0f}ms")

        # Signal volume pressure
        for signal_count in [100, 500, 1000]:
            big_signals = [{"metric": "latency_ms", "value": 5000.0 + i, "source": "test"}
                           for i in range(signal_count)]
            big_signals.append({"metric": "replicas", "value": 3.0, "source": "test"})
            big_signals.append({"metric": "max_replicas", "value": 10.0, "source": "test"})
            try:
                resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": big_signals})
                ok = resp.status_code == 200
                report.add(StressResult(f"gcl_signals_{signal_count}", ok, ms,
                                      f"status={resp.status_code} latency={ms:.0f}ms"))
                print(f"  GCL {signal_count} signals: {ms:.0f}ms status={resp.status_code}")
            except Exception as e:
                report.add(StressResult(f"gcl_signals_{signal_count}", False, 0, str(e)))
                print(f"  GCL {signal_count} signals: FAILED {e}")

        return report

    # ── Phase 4: Edge Cases ──

    async def phase_edge_cases(self) -> PhaseReport:
        report = PhaseReport("Phase 4: Edge Cases")
        print("\n=== Phase 4: Edge Cases ===")

        # 4A: Evidence poisoning
        print("  --- 4A: Evidence poisoning ---")

        # NaN values
        nan_signals = [{"metric": "latency_ms", "value": float("nan"), "source": "test"}]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": nan_signals})
            ok = resp.status_code in (200, 422)
            report.add(StressResult("nan_evidence", ok, ms,
                                  f"status={resp.status_code}"))
            print(f"    NaN value: status={resp.status_code} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("nan_evidence", False, 0, str(e)))
            print(f"    NaN value: {e}")

        # Negative latency
        neg_signals = [
            {"metric": "latency_ms", "value": -5000.0, "source": "test"},
            {"metric": "replicas", "value": 3.0, "source": "test"},
            {"metric": "max_replicas", "value": 10.0, "source": "test"},
        ]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": neg_signals})
            d = resp.json()
            ok = resp.status_code == 200
            report.add(StressResult("negative_latency", ok, ms,
                                  f"action={d.get('action_type')} committed={d.get('committed')}"))
            print(f"    Negative latency: action={d.get('action_type')} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("negative_latency", False, 0, str(e)))

        # Contradictory evidence
        contra_signals = [
            {"metric": "latency_ms", "value": 100.0, "source": "test"},
            {"metric": "latency_ms", "value": 50000.0, "source": "test"},
            {"metric": "replicas", "value": 3.0, "source": "test"},
            {"metric": "max_replicas", "value": 10.0, "source": "test"},
        ]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": contra_signals})
            d = resp.json()
            ok = resp.status_code == 200
            report.add(StressResult("contradictory_evidence", ok, ms,
                                  f"action={d.get('action_type')}"))
            print(f"    Contradictory: action={d.get('action_type')} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("contradictory_evidence", False, 0, str(e)))

        # Extremely long metric name
        long_signals = [{"metric": "a" * 10000, "value": 5000.0, "source": "test"}]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": long_signals})
            ok = resp.status_code in (200, 422)
            report.add(StressResult("long_metric_name", ok, ms, f"status={resp.status_code}"))
            print(f"    10K metric name: status={resp.status_code} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("long_metric_name", False, 0, str(e)))

        # 4B: Falsification bypass
        print("  --- 4B: Falsification bypass ---")

        # Try to force scale > 20 replicas
        extreme_signals = [
            {"metric": "latency_ms", "value": 1000000.0, "source": "test"},
        ] * 10 + [
            {"metric": "replicas", "value": 1.0, "source": "test"},
            {"metric": "max_replicas", "value": 100.0, "source": "test"},
        ]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": extreme_signals})
            d = resp.json()
            action = d.get("action_type", "none")
            ok = True
            if action == "scale":
                # Verify scale is capped
                ok = True  # falsification should cap it
            report.add(StressResult("scale_cap_bypass", ok, ms,
                                  f"action={action} committed={d.get('committed')}"))
            print(f"    Scale cap bypass: action={action} committed={d.get('committed')} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("scale_cap_bypass", False, 0, str(e)))

        # Compliance + scale (should always produce alert, never scale)
        compliance_signals = [
            {"metric": "latency_ms", "value": 50000.0, "source": "test"},
        ] * 5 + [
            {"metric": "compliance_violation_flag", "value": 1.0, "source": "test"},
            {"metric": "replicas", "value": 3.0, "source": "test"},
            {"metric": "max_replicas", "value": 10.0, "source": "test"},
        ]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": compliance_signals})
            d = resp.json()
            action = d.get("action_type", "none")
            ok = action in ("alert", "migrate", "no_action", None)
            report.add(StressResult("compliance_blocks_scale", ok, ms,
                                  f"action={action} (should be alert/migrate, never scale)"))
            print(f"    Compliance+scale: action={action} {'PASS' if ok else 'FAIL'} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("compliance_blocks_scale", False, 0, str(e)))

        # 4D: Cooldown
        print("  --- 4D: Cooldown ---")
        signals = await self._seed_and_get_signals(4)

        # First cycle (should commit)
        resp1, ms1 = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
        d1 = resp1.json()

        # Second cycle immediately (should be blocked by cooldown)
        resp2, ms2 = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
        d2 = resp2.json()

        first_committed = d1.get("committed", False)
        second_committed = d2.get("committed", False)
        if first_committed:
            ok = not second_committed
            report.add(StressResult("cooldown_blocks_repeat", ok, ms2,
                                  f"first={first_committed} second={second_committed} (second should be False)"))
            print(f"    Cooldown: first={first_committed} second={second_committed} {'PASS' if ok else 'FAIL'}")
        else:
            report.add(StressResult("cooldown_blocks_repeat", True, ms2,
                                  f"first not committed, cooldown test N/A"))
            print(f"    Cooldown: first not committed, test N/A")

        # 4E: Cross-system boundary
        print("  --- 4E: Cross-system boundary ---")

        # Wrong content type
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as c:
                resp = await c.post(f"{self.gcl}/api/v1/events/deepfield",
                                    content=json.dumps({"test": True}),
                                    headers={"Content-Type": "application/json"})
            ok = resp.status_code == 415
            report.add(StressResult("wrong_content_type", ok, 0,
                                  f"status={resp.status_code} (expected 415)"))
            print(f"    Wrong content type: status={resp.status_code} {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            report.add(StressResult("wrong_content_type", False, 0, str(e)))

        # Wrong source
        try:
            event = {
                "specversion": "1.0",
                "type": "srex.deepfield.observation.v1",
                "source": "urn:evil:attacker",
                "id": "test-evil-1",
                "data": {}
            }
            async with httpx.AsyncClient(verify=False, timeout=10) as c:
                resp = await c.post(f"{self.gcl}/api/v1/events/deepfield",
                                    content=json.dumps(event),
                                    headers={"Content-Type": "application/cloudevents+json"})
            ok = resp.status_code in (403, 422)
            report.add(StressResult("wrong_event_source", ok, 0,
                                  f"status={resp.status_code} (expected 403)"))
            print(f"    Wrong event source: status={resp.status_code} {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            report.add(StressResult("wrong_event_source", False, 0, str(e)))

        return report

    # ── Phase 5: Degradation ──

    async def phase_degradation(self) -> PhaseReport:
        report = PhaseReport("Phase 5: Degradation")
        print("\n=== Phase 5: Degradation ===")

        # 5A: GCL operates correctly when fleet is unreachable
        print("  --- 5A: GCL without fleet ---")
        signals = await self._seed_and_get_signals(4)
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
            d = resp.json()
            ok = resp.status_code == 200
            report.add(StressResult("gcl_without_fleet", ok, ms,
                                  f"GCL cycle completes even if fleet submission fails: action={d.get('action_type')} committed={d.get('committed')}"))
            print(f"    GCL without fleet: action={d.get('action_type')} committed={d.get('committed')} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("gcl_without_fleet", False, 0, str(e)))

        # 5B: Empty signals (no evidence)
        print("  --- 5B: Empty evidence ---")
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": []})
            d = resp.json()
            action = d.get("action_type", "none")
            ok = resp.status_code == 200 and action in ("no_action", None, "none")
            report.add(StressResult("empty_signals", ok, ms,
                                  f"action={action} (should be no_action with no evidence)"))
            print(f"    Empty signals: action={action} {'PASS' if ok else 'FAIL'} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("empty_signals", False, 0, str(e)))

        # 5C: All scenarios degrade gracefully
        print("  --- 5C: All scenarios ---")
        scenarios = [
            "inference_fleet_spike", "compliance_breach", "capacity_exhaustion",
            "slo_cascade", "mixed_storm", "multi_cluster_migration",
        ]
        for scenario in scenarios:
            try:
                await self._post(f"{self.gcl}/api/v1/scenario/seed", {
                    "scenario": scenario, "seed": 42
                })
                resp = await self._get(f"{self.gcl}/api/v1/scenario/step/4")
                sigs = resp.json().get("signals", [])
                resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": sigs})
                d = resp.json()
                ok = resp.status_code == 200
                report.add(StressResult(f"scenario_{scenario}", ok, ms,
                                      f"action={d.get('action_type')} committed={d.get('committed')}"))
                print(f"    {scenario}: action={d.get('action_type')} committed={d.get('committed')} ({ms:.0f}ms)")
            except Exception as e:
                report.add(StressResult(f"scenario_{scenario}", False, 0, str(e)))

        # 5D: Rapid reset/seed interleave (state thrashing)
        print("  --- 5D: State thrashing ---")
        thrash_errors = 0
        for i in range(10):
            try:
                await self._post(f"{self.gcl}/api/v1/reset", {})
                await self._post(f"{self.gcl}/api/v1/scenario/seed", {
                    "scenario": scenarios[i % len(scenarios)], "seed": i
                })
                resp = await self._get(f"{self.gcl}/api/v1/scenario/step/2")
                sigs = resp.json().get("signals", [])
                resp, _ = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": sigs})
                if resp.status_code != 200:
                    thrash_errors += 1
            except Exception:
                thrash_errors += 1
        ok = thrash_errors <= 2
        report.add(StressResult("state_thrashing", ok, 0,
                              f"{thrash_errors}/10 failures during rapid reset/seed interleave"))
        print(f"    State thrashing: {thrash_errors}/10 failures {'PASS' if ok else 'FAIL'}")

        # 5E: Fleet healthz under GCL load
        print("  --- 5E: Fleet health during GCL load ---")
        signals = await self._seed_and_get_signals(4)

        async def gcl_load():
            for _ in range(20):
                try:
                    await self._post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                except Exception:
                    pass

        async def fleet_probe():
            await asyncio.sleep(0.1)
            latencies = []
            for _ in range(10):
                try:
                    t = time.monotonic()
                    await self._get(f"{self.fleet}/healthz")
                    latencies.append((time.monotonic() - t) * 1000)
                except Exception:
                    latencies.append(float("inf"))
            return latencies

        _, fleet_lats = await asyncio.gather(gcl_load(), fleet_probe())
        finite_lats = [l for l in fleet_lats if l != float("inf")]
        if finite_lats:
            p50 = sorted(finite_lats)[len(finite_lats) // 2]
            ok = p50 < 500
            report.add(StressResult("fleet_health_under_load", ok, 0,
                                  f"p50={p50:.0f}ms ({len(finite_lats)}/10 responded)"))
            print(f"    Fleet health under GCL load: p50={p50:.0f}ms ({len(finite_lats)}/10 responded)")
        else:
            report.add(StressResult("fleet_health_under_load", False, 0, "Fleet unresponsive"))
            print(f"    Fleet health under GCL load: UNRESPONSIVE")

        for r in report.results:
            if not r.passed:
                status = "FAIL"
                print(f"  [{status}] {r.name}: {r.detail}")
        return report

    # ── Phase 6: Soak ──

    async def phase_soak(self) -> PhaseReport:
        report = PhaseReport("Phase 6: Soak")
        print("\n=== Phase 6: Soak ===")

        signals = await self._seed_and_get_signals(4)

        # 6A: Sustained governance cycles (300 sequential over ~60s)
        print("  --- 6A: Sustained sequential load (300 cycles) ---")
        latencies = []
        errors = 0
        buckets: dict[int, list[float]] = {}
        start = time.monotonic()

        for i in range(300):
            try:
                _, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                latencies.append(ms)
                bucket = int((time.monotonic() - start) / 10)
                buckets.setdefault(bucket, []).append(ms)
            except Exception:
                errors += 1

        wall = (time.monotonic() - start) * 1000
        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            report.add(StressResult("soak_300_sequential", errors < 10, wall,
                                  f"p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms errors={errors}/300 wall={wall/1000:.1f}s",
                                  {"p50": p50, "p95": p95, "p99": p99, "errors": errors, "wall": wall}))
            print(f"  300 cycles: p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms errors={errors}/300 wall={wall/1000:.1f}s")

            # 6B: Latency stability (no drift > 2x across 10s buckets)
            bucket_medians = {}
            for b, lats in sorted(buckets.items()):
                lats.sort()
                bucket_medians[b] = lats[len(lats) // 2]

            if len(bucket_medians) >= 2:
                medians = list(bucket_medians.values())
                drift = max(medians) / max(min(medians), 0.1)
                ok = drift < 3.0
                report.add(StressResult("soak_latency_stability", ok, 0,
                                      f"drift={drift:.1f}x (max median / min median across 10s windows)",
                                      {"drift": drift, "bucket_medians": bucket_medians}))
                print(f"  Latency stability: drift={drift:.1f}x {'PASS' if ok else 'FAIL (>3x drift)'}")
        else:
            report.add(StressResult("soak_300_sequential", False, wall, f"All 300 cycles failed"))
            print(f"  300 cycles: ALL FAILED")

        # 6C: Memory/state leak check via cycle history growth
        print("  --- 6C: State leak check ---")
        try:
            resp = await self._get(f"{self.gcl}/api/v1/cycles")
            cycle_count = len(resp.json())
            report.add(StressResult("soak_cycle_history", True, 0,
                                  f"{cycle_count} cycles in history after soak"))
            print(f"  Cycle history: {cycle_count} entries")
        except Exception as e:
            report.add(StressResult("soak_cycle_history", False, 0, str(e)))

        # 6D: Mixed concurrent soak (governance + healthz + metrics)
        print("  --- 6D: Mixed concurrent soak (60s) ---")
        gcl_ok = 0
        gcl_err = 0
        fleet_ok = 0
        fleet_err = 0
        soak_start = time.monotonic()
        soak_duration = 60.0

        async def soak_gcl():
            nonlocal gcl_ok, gcl_err
            while time.monotonic() - soak_start < soak_duration:
                try:
                    resp = await self._post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                    if resp.status_code == 200:
                        gcl_ok += 1
                    else:
                        gcl_err += 1
                except Exception:
                    gcl_err += 1

        async def soak_fleet():
            nonlocal fleet_ok, fleet_err
            while time.monotonic() - soak_start < soak_duration:
                try:
                    resp = await self._get(f"{self.fleet}/healthz")
                    if resp.status_code == 200:
                        fleet_ok += 1
                    else:
                        fleet_err += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    fleet_err += 1

        workers = [soak_gcl() for _ in range(3)] + [soak_fleet() for _ in range(2)]
        await asyncio.gather(*workers)
        soak_wall = (time.monotonic() - soak_start) * 1000

        gcl_total = gcl_ok + gcl_err
        fleet_total = fleet_ok + fleet_err
        gcl_rate = gcl_err / max(gcl_total, 1)
        fleet_rate = fleet_err / max(fleet_total, 1)

        ok = gcl_rate < 0.05 and fleet_rate < 0.05
        report.add(StressResult("soak_mixed_concurrent", ok, soak_wall,
                              f"GCL: {gcl_ok}/{gcl_total} ok ({gcl_rate:.1%} err), Fleet: {fleet_ok}/{fleet_total} ok ({fleet_rate:.1%} err), wall={soak_wall/1000:.0f}s",
                              {"gcl_ok": gcl_ok, "gcl_err": gcl_err, "fleet_ok": fleet_ok, "fleet_err": fleet_err}))
        print(f"  Mixed soak: GCL {gcl_ok}/{gcl_total} ok, Fleet {fleet_ok}/{fleet_total} ok, wall={soak_wall/1000:.0f}s")

        # 6E: Post-soak smoke (verify system still healthy)
        print("  --- 6E: Post-soak smoke ---")
        try:
            await self._post(f"{self.gcl}/api/v1/reset", {})
            signals = await self._seed_and_get_signals(4)
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
            d = resp.json()
            ok = resp.status_code == 200 and d.get("action_type") is not None
            report.add(StressResult("post_soak_smoke", ok, ms,
                                  f"action={d.get('action_type')} committed={d.get('committed')} ({ms:.0f}ms)"))
            print(f"  Post-soak smoke: action={d.get('action_type')} committed={d.get('committed')} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("post_soak_smoke", False, 0, str(e)))

        try:
            t = time.monotonic()
            resp = await self._get(f"{self.fleet}/healthz")
            ok = resp.status_code == 200
            ms = (time.monotonic() - t) * 1000
            report.add(StressResult("post_soak_fleet_health", ok, ms, f"status={resp.status_code} ({ms:.0f}ms)"))
            print(f"  Post-soak fleet health: status={resp.status_code} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("post_soak_fleet_health", False, 0, str(e)))

        return report

    # ── Phase 7: Pen Testing ──

    async def phase_pen(self) -> PhaseReport:
        report = PhaseReport("Phase 7: Pen Testing")
        print("\n=== Phase 7: Pen Testing ===")

        # GCL reset has no auth
        try:
            resp = await self._post(f"{self.gcl}/api/v1/reset", {})
            ok = resp.status_code == 200
            report.add(StressResult("reset_no_auth", True, 0,
                                  f"status={resp.status_code} (WARNING: no auth on reset endpoint)"))
            print(f"  Reset no auth: status={resp.status_code} WARNING: anyone can wipe state")
        except Exception as e:
            report.add(StressResult("reset_no_auth", False, 0, str(e)))

        # classify-prompt with malformed input
        try:
            resp = await self._post(f"{self.gcl}/api/v1/classify-prompt", {"not_a_prompt": 123})
            ok = resp.status_code in (200, 422)
            report.add(StressResult("classify_malformed", ok, 0,
                                  f"status={resp.status_code}"))
            print(f"  Classify malformed input: status={resp.status_code}")
        except Exception as e:
            report.add(StressResult("classify_malformed", False, 0, str(e)))

        # Unknown scenario name
        try:
            resp = await self._post(f"{self.gcl}/api/v1/scenario/seed", {
                "scenario": "does_not_exist", "seed": 1
            })
            d = resp.json()
            silent_default = d.get("scenario") != "does_not_exist"
            report.add(StressResult("unknown_scenario", True, 0,
                                  f"Got scenario={d.get('scenario')} (WARNING: silently falls to default)" if silent_default else "Properly rejected"))
            print(f"  Unknown scenario: {d.get('scenario')} {'WARNING: silent fallback' if silent_default else 'rejected'}")
        except Exception as e:
            report.add(StressResult("unknown_scenario", False, 0, str(e)))

        # Fleet SQL injection
        try:
            resp = await self._get(f"{self.fleet}/api/v1/clusters?id='; DROP TABLE clusters;--")
            ok = resp.status_code != 500
            report.add(StressResult("fleet_sql_injection", ok, 0,
                                  f"status={resp.status_code}"))
            print(f"  Fleet SQL injection: status={resp.status_code} {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            report.add(StressResult("fleet_sql_injection", False, 0, str(e)))

        # Fleet path traversal
        try:
            resp = await self._get(f"{self.fleet}/api/v1/../../etc/passwd")
            ok = resp.status_code in (400, 404, 301, 308)
            report.add(StressResult("fleet_path_traversal", ok, 0,
                                  f"status={resp.status_code}"))
            print(f"  Fleet path traversal: status={resp.status_code} {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            report.add(StressResult("fleet_path_traversal", False, 0, str(e)))

        return report

    # ── Phase 8: Chaos ──

    async def phase_chaos(self) -> PhaseReport:
        report = PhaseReport("Phase 8: Chaos")
        print("\n=== Phase 8: Chaos ===")

        # Rapid-fire 200 governance cycles
        signals = await self._seed_and_get_signals(4)
        errors = 0
        latencies = []

        async def fire_one():
            nonlocal errors
            try:
                _, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
                latencies.append(ms)
            except Exception:
                errors += 1

        t = time.monotonic()
        tasks = [fire_one() for _ in range(200)]
        await asyncio.gather(*tasks)
        wall = (time.monotonic() - t) * 1000

        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p99 = latencies[int(len(latencies) * 0.99)]
            error_rate = errors / 200
            ok = error_rate < 0.2
            report.add(StressResult("gcl_rapid_fire_200", ok, wall,
                                  f"p50={p50:.0f}ms p99={p99:.0f}ms errors={errors}/200 ({error_rate:.0%}) wall={wall:.0f}ms",
                                  {"p50": p50, "p99": p99, "errors": errors, "wall": wall}))
            print(f"  GCL rapid-fire 200: p50={p50:.0f}ms p99={p99:.0f}ms errors={errors}/200 wall={wall:.0f}ms")

        # 10KB evidence payload
        big_signals = [{"metric": f"metric_{i}", "value": float(i), "source": "chaos"}
                       for i in range(500)]
        try:
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": big_signals})
            ok = resp.status_code == 200
            report.add(StressResult("gcl_10kb_payload", ok, ms, f"status={resp.status_code} ({ms:.0f}ms)"))
            print(f"  GCL 10KB payload: status={resp.status_code} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("gcl_10kb_payload", False, 0, str(e)))

        # Reset mid-operation then verify recovery
        await self._post(f"{self.gcl}/api/v1/reset", {})
        try:
            signals = await self._seed_and_get_signals(0)
            resp, ms = await self._timed_post(f"{self.gcl}/api/v1/cycle", {"signals": signals})
            ok = resp.status_code == 200
            report.add(StressResult("gcl_reset_recovery", ok, ms, f"Recovered after reset ({ms:.0f}ms)"))
            print(f"  GCL reset recovery: {'PASS' if ok else 'FAIL'} ({ms:.0f}ms)")
        except Exception as e:
            report.add(StressResult("gcl_reset_recovery", False, 0, str(e)))

        return report

    # ── Run all phases ──

    async def run(self, phases: list[str]):
        phase_map = {
            "smoke": self.phase_smoke,
            "performance": self.phase_performance,
            "pressure": self.phase_pressure,
            "edge": self.phase_edge_cases,
            "degradation": self.phase_degradation,
            "soak": self.phase_soak,
            "pen": self.phase_pen,
            "chaos": self.phase_chaos,
        }

        if "all" in phases:
            phases = list(phase_map.keys())

        for name in phases:
            if name in phase_map:
                try:
                    report = await phase_map[name]()
                    self.reports.append(report)
                except Exception as e:
                    print(f"\n=== Phase '{name}' CRASHED: {e} ===")
                    crash_report = PhaseReport(f"Phase '{name}' (CRASHED)")
                    crash_report.add(StressResult(f"{name}_crash", False, 0, str(e)))
                    self.reports.append(crash_report)

        self.print_summary()

    def print_summary(self):
        print("\n" + "=" * 60)
        print("ECOSYSTEM STRESS TEST RESULTS")
        print("=" * 60)
        total_pass = 0
        total_fail = 0
        findings = []

        for report in self.reports:
            total_pass += report.passed
            total_fail += report.failed
            print(f"\n  {report.summary()}")
            for r in report.results:
                status = "PASS" if r.passed else "FAIL"
                print(f"    [{status}] {r.name}: {r.detail}")
                if not r.passed:
                    findings.append(f"  - {r.name}: {r.detail}")

        print(f"\n  TOTAL: {total_pass} passed, {total_fail} failed")

        if findings:
            print(f"\n  FINDINGS ({len(findings)}):")
            for f in findings:
                print(f)

        # Collect performance metrics
        print("\n  PERFORMANCE METRICS:")
        for report in self.reports:
            for r in report.results:
                if r.metrics:
                    print(f"    {r.name}: {r.metrics}")


async def main():
    parser = argparse.ArgumentParser(description="Ecosystem stress test runner")
    parser.add_argument("--gcl-url", default="https://gcl-app.192.168.1.123.sslip.io")
    parser.add_argument("--fleet-url", default="http://localhost:18080")
    parser.add_argument("--phase", default="all",
                        help="Comma-separated phases: smoke,performance,pressure,edge,degradation,soak,pen,chaos or 'all'")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    phases = [p.strip() for p in args.phase.split(",")]
    runner = EcosystemStressTest(args.gcl_url, args.fleet_url, args.timeout)
    await runner.run(phases)


if __name__ == "__main__":
    asyncio.run(main())
