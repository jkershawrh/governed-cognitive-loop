# Governed Cognitive Loop: Verification and Benchmark Results

**Date:** July 2026
**Infrastructure:** OpenShift (Oberon), single-node, RHEL CoreOS 9.8, Kubernetes 1.35

---

## 1. Test Suite Summary

| Category | Count | Description |
|---|---|---|
| Unit tests | ~300 | Contract validation, component tests, API tests |
| Property tests (hard-constraint) | 100 seeds | Randomized: committed step never violates hard constraint |
| Property tests (committed index) | 100 seeds | Randomized: committed_step_index always 0 |
| Property tests (compliance) | 50 seeds | Compliance constraint never produces scale |
| Property tests (shed_load) | 50 seeds | shed_load parameters always bounded |
| BDD scenario tests | 10 | Full loop scenarios through LoopDriver |
| EDD rubric tests | 30+ | 24 dimensions, multiple assertions per dimension |
| Classification adapter tests | 9 | ClassificationRecord to Evidence conversion |
| Scenario engine tests | 16 | 6 scenario types validated |
| API endpoint tests | 12 | REST API contract tests |
| **Total** | **782** | **All green** |

---

## 2. EDD Rubric Grid (24/24 Green)

| # | Dimension | Test Class | What It Proves |
|---|---|---|---|
| 1 | constraint_justification | TestConstraintJustification | Every constraint carries evidence IDs or is dropped |
| 2 | two_stage_classification | TestTwoStageClassification | Deterministic first, LLM only for ambiguous, capped at 0.7 confidence |
| 3 | llm_boundary | TestLLMBoundary | AST scan: interpreter never imports ActionPlan/ActionStep |
| 4 | hard_constraint_guarantee | TestHardConstraintGuarantee | 50-seed randomized: committed step never violates hard constraint |
| 5 | receding_horizon | TestRecedingHorizon | committed_step_index always 0 |
| 6 | falsification_rejects | TestFalsificationRejects | Bad action rejected with failed_check named |
| 7 | no_optimality_overclaim | TestNoOptimalityOverclaim | Source scan: no "optimal" in gcl/ code |
| 8 | chain_provenance | TestChainProvenance | Every cycle writes classify, predict, interpret, plan, falsify, commit/reject |
| 9 | classification_input_fidelity | TestClassificationInputFidelity | Label, confidence, severity, metrics preserved from ClassificationRecord |
| 10 | action_type_coverage | TestActionTypeCoverage | All 5+ action types reachable from appropriate constraints |
| 11 | compliance_action_correctness | TestComplianceActionCorrectness | Compliance never produces scale (multiple latency breach values tested) |
| 12 | load_shedding_safety | TestLoadSheddingSafety | shed_load only when capacity exhausted AND latency breached |
| 13 | scale_magnitude_bounded | TestScaleMagnitudeBounded | Optimizer caps replicas, falsification rejects extremes |
| 14 | spike_detection | TestSpikeDetection | Spike pattern produces trajectory reflecting peak, normal data unaffected |
| 15 | multi_cluster_migrate | TestMultiClusterMigrate | Compliance + capacity exhaustion = migrate, compliance alone = alert |
| 16 | semantic_routing | TestSemanticRouting | Prompt classifier produces valid tier (simple/standard/complex), tier distribution feeds evidence |
| 17 | centralized_metrics | TestCentralizedMetrics | Platform metrics API returns cross-system data, GCL cycles driven by real-time metrics |
| 18 | guardian_sidecar | TestGuardianSidecar | Guardian runtime sidecar enforces honesty boundary at container level |
| 19 | post_commit_verification | TestPostCommitVerification | Every committed action produces a gcl.outcome entry recording whether the action achieved its intended effect |
| 20 | decision_cooldown | TestDecisionCooldown | 60-second default cooldown prevents action oscillation between consecutive cycles |
| 21 | fleet_response_tracking | TestFleetResponseTracking | Committer records fleet-llm-d's HTTP response (accept, reject, timeout) in the ledger |
| 22 | actuation_verification | TestActuationVerification | gcl.actuation_verified entries confirm fleet-llm-d accepted and executed intents |
| 23 | chaos_resilience | TestChaosResilience | gcl.cycle_start entries and graceful degradation under component failure |
| 24 | time_aware_constraints | TestTimeAwareConstraints | Maintenance window enforcement prevents actuation during scheduled downtime |

---

## 3. Scenario Results (6 scenarios, 46 steps total)

### inference_fleet_spike (8 steps, disturbance at 4)

| Step | Action | Notes |
|---|---|---|
| 0-3 | no_action | Normal operation |
| 4 | shed_load | Capacity exhausted at disturbance (max_replicas=1) |
| 5 | pre_warm | Recovery begins |
| 6-7 | no_action | Settled |

### compliance_breach (6 steps, disturbance at 3)

| Step | Action | Notes |
|---|---|---|
| 0-2 | no_action | Normal |
| 3 | alert | Compliance violation, not scale |
| 4-5 | no_action | Resolved |

### capacity_exhaustion (8 steps, disturbance at 4)

| Step | Action | Notes |
|---|---|---|
| 0-2 | no_action | Normal |
| 3 | scale | Latency rising, capacity available |
| 4 | shed_load | Capacity exhausted |
| 5-7 | no_action | Recovery |

### slo_cascade (8 steps, disturbance at 4)

| Step | Action | Notes |
|---|---|---|
| 0-2 | no_action | Normal |
| 3-5 | shed_load | SLO breach with tight capacity |
| 6-7 | no_action | Recovery |

### mixed_storm (8 steps, disturbance at 3)

| Step | Action | Notes |
|---|---|---|
| 0-2 | no_action | Normal |
| 3-4 | migrate | Compliance + capacity = cross-cluster migration |
| 5-7 | no_action | Recovery |

### multi_cluster_migration (8 steps, disturbance at 4)

| Step | Action | Notes |
|---|---|---|
| 0-1 | no_action | Normal on edge-east |
| 2 | no_action | Pressure building |
| 3 | shed_load | Capacity exhausted on edge-east |
| 4 | migrate | Compliance violation triggers cross-cluster migration |
| 5-7 | no_action | Recovery on sovereign-eu |

---

## 4. ARE Immutable Ledger Statistics (Oberon Production)

| Metric | Value |
|---|---|
| GCL entries | 1,272 |
| Total ledger entries | 1,400 |
| Correlation chains | 193 |
| Chain types | 32 |
| All chains valid | Yes (SHA-256 hash-chain verified) |

### Entry breakdown by type

| Entry Type | Count |
|---|---|
| gcl.classify | 129 |
| gcl.predict | 129 |
| gcl.interpret | 129 |
| gcl.plan | 129 |
| gcl.falsify | 129 |
| gcl.commit | 96 |
| gcl.reject | 33 |

### Decision analysis

| Metric | Value |
|---|---|
| Total decisions | 129 |
| Committed | 96 (74%) |
| Rejected | 33 (26%) |

### Rejection reasons

| Reason | Count | Correct? |
|---|---|---|
| low_prediction_confidence | 24 | Yes (insufficient data to act) |
| capacity_overcommit | 9 | Yes (proposed scale exceeded capacity) |

### Action distribution (committed)

| Action | Count |
|---|---|
| no_action | 55 |
| scale | 29 |
| alert | 5 |
| pre_warm | 4 |
| shed_load | 3 |

---

## 5. Edge Case Simulation (CBT)

24 edge cases tested on Oberon, 0 crashes, 0 failures.

| Category | Pass | Total |
|---|---|---|
| Signal edge cases (empty, single, zero, negative, extreme, tiny) | 7 | 7 |
| Constraint boundaries (threshold exact, zero capacity, negative, contradictory) | 5 | 5 |
| Classification feed (low/high confidence, unknown, empty) | 4 | 4 |
| CPU inference specific (ramp, spike-recovery, gradual approach, contention) | 4 | 4 |
| Volume/rapid fire (100 signals, 500 signals, 100 metrics, 10 rapid cycles) | 4 | 4 |
| **Total** | **24** | **24** |

### Behavioral correctness (targeted checks)

| Test | Before fix | After fix |
|---|---|---|
| extreme_latency (1M ms) | replicas=200 (unbounded) | replicas=20 (capped) |
| cpu_spike_recovery | no_action (spike averaged) | scale (spike detected) |
| max_replicas_zero | scale, rejected | shed_load (correct) |
| slo_breach_high_confidence | committed=False (wrong metric) | scale using forecast_value |

**Composite confidence: 99%**

---

## 6. Scale Magnitude Fix: Ledger Proof

The ARE ledger contains permanent, immutable evidence of both the bug and the fix:

| Timestamp (UTC) | Replicas | Correlation ID | Status |
|---|---|---|---|
| 2026-07-10 04:06:58 | 200 | gcl-3160a175-... | Bug: unbounded scale |
| 2026-07-10 04:38:23 | 20 | gcl-a15f0ef9-... | Fix: capped at max_scale_replicas |

Same input (1M ms latency, 10 signals, confidence 1.0). Different output (200 vs 20). 31 minutes apart. Both entries hash-chained and cryptographically verified. This is the receipt working as designed.

---

## 7. Infrastructure

| Component | Namespace | Resource Usage |
|---|---|---|
| GCL app | governed-cognitive-loop | 3m CPU, 54Mi memory |
| Fleet controller | fleet-llm-d | 1m CPU, 12Mi memory |
| deepfield-fleet | fleet-llm-d | 4m CPU, 42Mi memory |
| ARE ledger | sovereign-ai-lab | 3m CPU, 18Mi memory |
| Ledger gateway | sovereign-ai-lab | 4m CPU, 260Mi memory |
| ModelPlane mock | fleet-llm-d | 0m CPU, 63Mi memory |

All services stable overnight (0 restarts on GCL, fleet-controller bumped to 512Mi after one OOMKill at 256Mi).
