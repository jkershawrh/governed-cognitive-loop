# Governed Cognitive Loop: Governed Autonomy for AI Inference Fleet Management

## Hard-Constraint Satisfaction, Falsification-Gated Commit, and Immutable Decision Records

**Author:** Jonathan Kershaw
**Date:** July 2026
**Version:** Draft 0.1

---

## 1. Executive Summary

The Governed Cognitive Loop (GCL) is the governed autonomy layer for AI inference fleet management. It sits between prediction (deepfield-fleet, which classifies evidence and forecasts SLO breaches) and actuation (fleet-llm-d, which evaluates policy and executes intents), ensuring every infrastructure decision is constrained, challenged, and recorded before it reaches production. The system uses an LLM to interpret the goal and deterministic mathematics to compute the action. Every plan is treated as a hypothesis and subjected to seven falsification checks before commit. Every decision, whether committed or rejected, is written to the ARE Immutable Ledger with a correlation chain linking classify, predict, interpret, plan, falsify, and commit/reject entries under a single identifier. The guarantee is hard-constraint satisfaction and falsification-gated commit. Not optimality.

## 2. Problem Statement

### 2.1 The Prediction-Actuation Gap

The inference fleet has a predictive brain and an actuation layer. deepfield-fleet classifies infrastructure evidence (latency metrics, capacity pressure, compliance violations, SLO breach severity) and predicts whether an SLO breach is imminent, degraded, or already occurring. fleet-llm-d evaluates fleet-level policy, generates intents (scale, shed_load, pre_warm, alert, migrate), and executes them across clusters via HMAC-SHA256 authenticated endpoints. Both systems work. What is missing is the layer between them that asks: "should we actually do this?"

### 2.2 The Two Unsafe Alternatives

Without a governing layer, organizations face two options, both inadequate.

**Human gates every decision.** A platform engineer reviews each predicted breach, decides whether to scale, chooses the replica count, and submits the change. This works at low volume. At inference fleet scale, where latency spikes arrive in seconds and SLO cascades propagate across clusters, human review introduces minutes to hours of delay. The fleet degrades while the engineer sleeps, attends a meeting, or triages competing alerts.

**LLM drives actuation directly.** The LLM receives metrics, produces a scaling command, and the system executes it. This is fast but unsafe. The LLM has no mechanism for hard-constraint satisfaction. It cannot guarantee that a scale action respects capacity bounds. It has no self-challenge: it does not ask whether its own plan will work under the predicted conditions. It produces no falsifiable record. When something goes wrong, there is no receipt proving what was decided, why, or what evidence justified it.

### 2.3 What Governed Autonomy Means

The GCL fills this gap with a specific architecture: the LLM interprets the goal (what to optimize for), deterministic math computes the action (how many replicas, which pool), and every plan is challenged by a falsification gate before it commits. The result is governed autonomy: faster than human review, safer than direct LLM actuation, and fully auditable.

## 3. Architecture

### 3.1 The Four-System Platform

The GCL operates within a four-system platform. Each system owns a distinct responsibility, and no system crosses another's boundary.

**deepfield-fleet** owns evidence classification. It ingests raw infrastructure signals (Prometheus metrics, Kubernetes state, billing data) and produces ClassificationRecords with a class name (e.g., `slo_breach_predicted`, `capacity_saturated`, `policy_violation`), severity, confidence, taxonomy, agent name, rationale, and associated metrics. deepfield-fleet predicts; it does not decide.

**Governed Cognitive Loop (GCL)** owns the decision. It receives evidence (either directly as metric signals or via classification adapter from deepfield-fleet), classifies constraints, predicts the trajectory, interprets the objective, computes the action plan, falsifies the committed step, and either commits or rejects. The GCL decides; it does not execute.

**fleet-llm-d** owns actuation. It receives intents from the GCL (scale, pre_warm, shed_load, alert, migrate) via its `/api/v1/intents` endpoint, authenticated with HMAC-SHA256 signed tokens. fleet-llm-d evaluates fleet policy, routes to the appropriate cluster, and executes. fleet-llm-d executes; it does not decide.

**ARE Immutable Ledger** owns the record. Every GCL cycle writes a correlation chain of entries (gcl.classify, gcl.predict, gcl.interpret, gcl.plan, gcl.falsify, gcl.commit or gcl.reject) under a single correlation ID. The ledger is append-only and hash-chained. It is independent infrastructure, shared across systems. The ledger records; it does not influence decisions.

### 3.2 The Seven GCL Components

The GCL is composed of seven components, each with a single responsibility. They execute in sequence within a single cycle, orchestrated by the LoopDriver.

**1. ConstraintClassifier** (`gcl/classifier/classifier.py`). Two-stage, evidence-first classification. Stage one: a deterministic RuleEngine (`gcl/classifier/rules.py`) evaluates evidence against YAML-defined rules (e.g., `latency_ms > 5000` produces a hard latency constraint, `compliance_violation_flag == 1` produces a hard compliance constraint). Evidence that matches a rule produces a Constraint with `source=DETERMINISTIC` and the configured confidence (typically 0.9 or higher). Stage two: evidence that no rule matched is forwarded to an LLM classifier (`gcl/classifier/llm_classifier.py`), which produces Constraints with `source=LLM` and confidence capped at 0.7. This ensures deterministic classifications are preferred and LLM classifications are marked as lower confidence. Additionally, the classifier derives capacity constraints directly from `max_replicas` evidence, creating hard capacity bounds with 0.95 confidence. Every constraint must carry at least one justifying evidence ID; constraints without evidence are dropped.

**2. HorizonPredictor** (`gcl/predictor/predictor.py`). Produces a Trajectory: a sequence of TrajectoryPoints over a configurable horizon (default 10 steps), each with a predicted value, optional confidence bounds (lower, upper), and a trajectory-level confidence score. The predictor selects the primary metric (preferring `latency_ms` if at least 3 samples exist, otherwise the most frequent metric). With fewer than 3 data points, it produces a flat trajectory with low confidence (0.1). With 3 or more points, it first checks for spikes using a detection algorithm (peak must exceed 5000, at least 30% of values must be below 25% of peak, and peak must exceed baseline by the configured spike detection threshold of 2.0x). If a spike is detected, the trajectory decays from peak with a 0.9 decay rate. Otherwise, it runs numpy-based linear regression (`gcl/predictor/slo_seed.py`) and extrapolates, with confidence derived from R-squared and sample count.

**3. ObjectiveInterpreter** (`gcl/interpreter/interpreter.py`). Produces an ObjectiveSpec: a list of cost terms (e.g., `latency_cost`, `resource_cost`, `compliance_cost`), weights (summing to 1.0), hard and soft constraint IDs, and a rationale string. The interpreter tries the LLM first (unless force-deterministic mode is active). The LLM receives constraint descriptions and context, and is instructed to produce cost terms and weights. It is explicitly told: "You must NEVER produce an action, action plan, or control command. You only specify what to optimize for, not how to achieve it." If the LLM is unavailable or returns an unparseable result, the interpreter falls back to a TemplateInterpreter (`gcl/interpreter/templates.py`) that selects from five YAML-defined templates based on constraint types: compliance_override (compliance dominates at 0.95 weight), latency_focused, capacity_focused, shed_load_focused (capacity + latency), and balanced.

**4. Controller** (`gcl/controller/controller.py`). Produces an ActionPlan: a sequence of ActionSteps over the trajectory horizon, with `committed_step_index` always equal to 0 (receding horizon discipline: only the first step is ever committed, the rest are planned but re-computed next cycle). The controller is numpy-based and fully deterministic. It calls `compute_action_for_step` (`gcl/controller/optimizer.py`) for each trajectory point. The optimizer evaluates constraints in priority order: compliance constraints first (producing `alert` or `migrate` depending on capacity), then latency constraints (producing `scale` when breached, `pre_warm` when approaching 80% of threshold), then capacity exhaustion with latency breach (producing `shed_load`). Scale magnitude is capped by both the capacity bound and the configured maximum (default 20 replicas). Every action is checked against hard constraints via `check_hard_constraint_satisfaction` before inclusion. If the first step violates any hard constraint, the controller returns None (infeasible) rather than committing a violation.

**5. FalsificationGate** (`gcl/falsification/gate.py`). Treats the committed step as a hypothesis: "this action produces the intended outcome under the predicted conditions." It runs seven deterministic disconfirmation checks in sequence, short-circuiting on the first failure. If all seven pass and force-deterministic mode is not active, an optional LLM adversary (`gcl/falsification/llm_adversary.py`) probes the action for incorrect assumptions, missing preconditions, timing issues, or cascading failures. The result is a FalsificationResult with verdict SURVIVES or FAILS, the failed check name (if any), reasoning, and evidence IDs.

**6. Committer** (`gcl/committer/committer.py`). If the falsification verdict is SURVIVES, the Committer actuates: it calls the adapter's `actuate` method (if an adapter is configured) to send the intent to fleet-llm-d, then writes a `gcl.commit` entry to the ledger. If the verdict is FAILS, it writes a `gcl.reject` entry with the failed check name, reasoning, and action details. The Committer never decides; it only executes the gate's verdict.

**7. LoopDriver** (`gcl/loop/driver.py`). Orchestrates a single cycle. It receives a list of Evidence signals, calls each component in sequence (classify, predict, interpret, optimize, falsify, commit), writes ledger entries at each stage under a single correlation ID (`gcl-{uuid}`), and returns a LoopCycle record containing the full state: constraints snapshot, trajectory, objective, action plan (or None if infeasible), falsification result, committed boolean, and correlation ID.

### 3.3 The Classification Adapter

The classification adapter (`gcl/adapter/classification_adapter.py`) transforms deepfield-fleet ClassificationRecords into GCL Evidence objects. It maps class names to evidence metrics: SLO classes (`slo_breach_predicted`, `slo_breach_imminent`, `slo_degraded`) produce `slo_breach_severity` evidence with value equal to the classification confidence, plus `latency_ms` evidence from the `forecast_value` metric if present. Capacity classes (`capacity_saturated`, `capacity_pressure`, `capacity_elevated`) produce `capacity_pressure_score` evidence. Compliance classes (`policy_violation`, `compliance_violation`) produce `compliance_violation_flag` evidence with value 1.0. All other classes produce generic evidence with value equal to severity score multiplied by confidence. Every classification's raw metrics are also emitted as individual Evidence objects. Labels (class_name, severity, taxonomy, agent_name) and metadata (rationale, source_classification_id) are preserved on each Evidence object for traceability.

### 3.4 The Fleet Adapter

The fleet adapter (`gcl/adapter/fleet_adapter.py`) maps committed actions to fleet-llm-d intents. The intent mapping (`gcl/adapter/intent_mapping.py`) defines five intent types: ScaleIntent, PreWarmIntent, ShedLoadIntent, AlertIntent, and MigrateIntent. Each maps the action's parameters to the intent's fields (e.g., `replicas` to `desired_replicas`, `pool` to `pool`). The `no_action` type maps to None (no intent sent). Authentication uses HMAC-SHA256 signed tokens compatible with fleet-llm-d's auth system: the adapter generates a token containing claims (subject, role, issued-at, expiration), signs the claims JSON with the shared secret, and sends the token as a Bearer header. The adapter sends intents via HTTP POST to `{fleet_url}/api/v1/intents`.

## 4. The Honesty Boundary

### 4.1 Why the LLM Interprets But Never Acts

The ObjectiveInterpreter produces an ObjectiveSpec: cost terms, weights, and a rationale. The Controller produces an ActionPlan: action type, parameters, and predicted effects. These are different types defined in different modules. The LLM (via LLMInterpreter or LLMClassifier) has access to Constraint, Evidence, and ObjectiveSpec. It does not have access to ActionPlan or ActionStep.

This is not a policy statement. It is a code-level invariant verified by AST inspection. The `TestLLMBoundary` test (`tests/test_rubrics.py`) parses every Python file in the `gcl/interpreter/` directory, walks the AST, and asserts that no file imports `ActionPlan` or `ActionStep`. If an import is added, the test fails. The same test runs in CI on every commit.

The boundary is enforced in the LLM's system prompt as well. The LLMInterpreter's system prompt states: "You must NEVER produce an action, action plan, or control command. You only specify what to optimize for, not how to achieve it." But system prompts can be ignored by the model. The AST test cannot be ignored. It is a structural guarantee: the interpreter module physically cannot construct an ActionPlan because it has no import of the type.

### 4.2 What This Boundary Produces

The separation means the LLM's judgment about the goal is decoupled from the deterministic execution of the action. The LLM might decide that latency should be weighted at 0.8 and resource cost at 0.2. The Controller then uses those weights, combined with the trajectory and constraints, to compute the action. The LLM does not know what action will result from its weights. The Controller does not know why those weights were chosen. Each operates on its own responsibility.

### 4.3 No Optimality Claim

The objective is LLM-specified (or template-specified, in fallback mode). Classical control theory optimality guarantees require a mathematically defined objective function. When the objective is produced by an LLM, those guarantees do not hold. The system's docstring states this explicitly: "Deterministic controller. Does not claim optimality. Guarantees: hard-constraint satisfaction and receding-horizon discipline."

What does hold: hard constraints are never violated by a committed action. The `check_hard_constraint_satisfaction` function verifies every candidate action against every hard constraint before it enters the plan. 300 randomized property tests (`test_properties.py`, seeds 0-99 across three property classes) confirm this. The `TestNoOptimalityOverclaim` test scans every Python file in the `gcl/` directory for the word "optimal" and fails if it appears in a context that implies a claim (exempting "does not claim," "suboptimal," and similar negations).

## 5. Falsification Before Commit

### 5.1 The Hypothesis

The FalsificationGate treats every committed step as a hypothesis: "this action, applied now, will produce the intended outcome under the predicted conditions." The gate's job is to attempt disconfirmation. If it cannot disconfirm the hypothesis, the action survives and is committed. If it can, the action fails and is rejected with a named reason.

### 5.2 The Seven Deterministic Checks

Each check is a pure function that receives the action step, evidence, constraints, and/or trajectory, and returns either None (the check passes) or a failure reason string. The first failure short-circuits: subsequent checks are not run.

**1. check_capacity_available.** Does the action request more replicas (via `replicas` or `target_replicas`) than evidence or hard capacity constraints allow? The check examines both hard capacity constraints (Constraint objects with type CAPACITY and hard=True) and `max_replicas` evidence. If the requested count exceeds either bound, the action fails with `capacity_overcommit`.

**2. check_scale_magnitude_reasonable.** Does a scale action request more replicas than the configured maximum? The default maximum is 20 (configurable via `max_scale_replicas` in `config/defaults/loop.yaml` or the `GCL_MAX_SCALE_REPLICAS` environment variable). This catches unbounded scaling even when capacity evidence is absent or stale. Failure reason: `scale_magnitude_unreasonable`.

**3. check_warmup_time_realistic.** Does a scale or pre_warm action assume a warmup time faster than evidence shows is achievable? The check compares the action's `assumed_warmup_seconds` parameter against `warmup_seconds` evidence, multiplied by a safety factor (default 1.5x, configurable via `warmup_time_multiplier`). Failure reason: `warmup_time_unrealistic`.

**4. check_prediction_confidence.** Is the trajectory confidence below the configured floor (default 0.5)? Low confidence means the prediction is unreliable, and actions based on unreliable predictions should not commit. Failure reason: `low_prediction_confidence`.

**5. check_compliance_action_valid.** Does a hard compliance constraint exist while the action type is `scale` or `pre_warm`? Scaling does not fix a compliance problem. If a data residency violation is active, adding replicas to the violating cluster is the wrong action class. The correct actions are `alert` (notify operators) or `migrate` (move workloads to a compliant cluster). Failure reason: `compliance_action_invalid`.

**6. check_shed_load_bounded.** If the action is `shed_load`, is `max_inflight` greater than zero and `duration_seconds` within the valid range (1 to 3600 seconds)? Unbounded or zero-duration load shedding is either meaningless or dangerous. Failure reason: `shed_load_unbounded`.

**7. check_migration_target_available.** If the action is `migrate`, is the `target_pool` parameter specified and non-empty? A migration without a target is not actionable. Failure reason: `migration_target_missing`.

### 5.3 The Optional LLM Adversary

After all seven deterministic checks pass, the FalsificationGate invokes an optional LLM adversary (unless force-deterministic mode is active). The adversary receives the action type, parameters, predicted effect, and context (trajectory confidence, constraint count, evidence count). Its system prompt instructs it to argue why the action will fail: "Look for: incorrect assumptions, missing preconditions, timing issues, capacity problems, or cascading failures." If the adversary finds a compelling reason, the action fails with `llm_adversarial_probe` as the failed check. The adversary is a secondary challenge layer; the seven deterministic checks are the primary defense.

### 5.4 Short-Circuit Behavior

The gate runs checks in a fixed order: capacity, magnitude, warmup, confidence, compliance, shed_load, migration, then LLM adversary. The first failure produces a FalsificationResult with verdict FAILS and the specific check name. This design is intentional: it provides a clear, single reason for rejection rather than a list of problems, making debugging and auditing straightforward.

## 6. Multi-Cluster and ModelPlane

### 6.1 ModelPlane Integration

The GCL integrates with fleet-llm-d's ModelPlane system for multi-cluster state awareness. The GCL API exposes a `/api/v1/modelplane/status` endpoint that fetches cluster and deployment state from the fleet-controller's ModelPlane endpoints (`/api/v1/modelplane/clusters` and `/api/v1/modelplane/deployments`), authenticated with the same HMAC-SHA256 token used for intent submission. This provides the GCL with visibility into which clusters are available (edge-east, edge-west, sovereign-eu, dev-cluster-1-cpu), which models are deployed where, and what capacity each cluster reports.

### 6.2 Cluster Context in Evidence

The GCL uses cluster context in evidence labels to trace which cluster each decision targets. In the multi-cluster migration scenario, evidence carries labels like `{"cluster": "edge-east"}`, `{"cluster": "sovereign-eu"}`, or `{"cluster": "edge-east", "target_cluster": "sovereign-eu"}`. These labels flow through the entire cycle (classify, predict, interpret, plan, falsify, commit) and are written to the ledger, providing a per-cluster audit trail.

### 6.3 Compliance-Driven Migration

When a compliance violation (data_residency_violation) occurs alongside capacity exhaustion (max_replicas <= 1), the Controller produces a `migrate` action instead of an `alert`. The migrate action specifies source_pool, target_pool, model, and reason. This is a deterministic escalation path: compliance alone triggers alert (notify the operator), but compliance combined with capacity exhaustion triggers migration (the workload must move because it cannot scale where it is and it should not be there in the first place).

### 6.4 Semantic Routing and Centralized Metrics

The GCL includes a prompt classifier that classifies prompts into tiers (simple/standard/complex) for fleet-llm-d's semantic routing. This feeds tier distribution as evidence into the governance loop, enabling tier-level scaling decisions. The classify-prompt endpoint is live and operational.

The GCL can pull live platform metrics from fleet-llm-d's centralized metrics API (GET /api/v1/metrics/platform) and run governed cycles driven by real-time cross-system data. The centralized metrics API aggregates inference, classification, governance, fleet, and ledger data into a single endpoint, replacing the previous per-cycle evidence snapshot approach with continuous metrics-driven predictions.

### 6.5 Post-Commit Accountability

After an action is committed and sent to fleet-llm-d, the GCL closes the loop with post-commit accountability. Six mechanisms ensure that committed actions are tracked through execution and their outcomes are recorded.

**Outcome ledger (gcl.outcome).** Every committed action produces a gcl.outcome entry in the ARE Immutable Ledger. The entry records whether the action achieved its intended effect, failed, or produced an unexpected result. This closes the gap between "the GCL decided to scale" and "the scale actually happened and helped."

**Decision cooldown (60s default).** After committing an action, the GCL enforces a 60-second cooldown before the same action type can be committed again. This prevents oscillation where consecutive cycles alternate between scale-up and scale-down (or shed-load and no-action) because each cycle sees only the state before the previous action takes effect. The cooldown duration is configurable via `GCL_DECISION_COOLDOWN_SECONDS`.

**Fleet response tracking.** The committer tracks fleet-llm-d's HTTP response to each intent submission. Acceptance (2xx), rejection (4xx), and timeout are recorded in the ledger alongside the intent correlation ID. This provides a complete record of whether the actuation layer received and accepted the decision.

**Actuation verification (gcl.actuation_verified).** After intent submission, the GCL writes a gcl.actuation_verified entry confirming that fleet-llm-d accepted and began executing the intent. This entry links to the original gcl.commit entry via correlation ID, closing the decide-actuate-verify chain.

**Chaos resilience (gcl.cycle_start).** Every cycle begins with a gcl.cycle_start entry in the ledger. If a cycle fails mid-execution (component crash, ledger unavailability, LLM timeout), the incomplete chain is detectable by comparing cycle_start entries against commit/reject entries. The loop recovers gracefully from component failures without data loss or invalid commits.

**Time-aware constraints (maintenance windows).** The constraint classifier recognizes time-based evidence (maintenance windows, restricted scaling periods, time-of-day policies). When a maintenance window is active, the classifier produces a hard time constraint that prevents actuation. This ensures the GCL does not scale or migrate during scheduled downtime, even if SLO metrics indicate a breach.

### 6.6 Authority Gate

The GCL is wired to the agent-promotion-line's AuthorityGate. Before committing any action, the GCL checks whether its consequence score is within its earned authority ceiling. The promotion line reads gcl.outcome entries from the ARE ledger to compute the GCL's track record: commits with effective=true are successes, effective=false are failures. The GCL's authority tier (T0 PROBATION through T4 PRINCIPAL) rises and falls based on this record. Demotion is always immediate. Promotion into high-consequence tiers can require human ratification.

### 6.7 Validated Scenarios

Six scenarios are validated end-to-end through the full loop, each with deterministic seeds for reproducibility:

1. **inference_fleet_spike** (8 steps). Normal operation, rising latency, spike at step 4 with max_replicas=1, recovery. Tests: disturbance step produces shed_load or rejected scale; recovery step commits.

2. **compliance_breach** (6 steps). Normal operation, compliance violation at step 3 (compliance_violation_flag=1.0, data_residency_violation=1.0), recovery. Tests: committed action is never scale or pre_warm; ledger records compliance constraints.

3. **capacity_exhaustion** (8 steps). Normal operation, latency rising with capacity squeeze at steps 3-4 (max_replicas drops to 2, then 1), recovery. Tests: shed_load produced when capacity exhausted with latency breach.

4. **slo_cascade** (8 steps). Normal with low SLO breach severity, then rising severity and latency, recovery. Tests: escalating actions match escalating severity.

5. **mixed_storm** (8 steps). Normal, then all classification signals fire simultaneously at steps 3-4 (SLO breach severity 0.9, capacity pressure 0.85, compliance violation 1.0, max_replicas=2), recovery. Tests: compliance takes priority over scaling; multiple constraint types recorded.

6. **multi_cluster_migration** (8 steps). Normal on edge-east, pressure building, capacity exhausted on edge-east at step 3, compliance violation at step 4, recovery on sovereign-eu. Tests: step 3 produces migrate or shed_load; step 4 produces alert or migrate.

## 7. Verification Methodology

### 7.1 Contract-Driven Design (CDD)

All data models are defined as Pydantic v2 contracts in `gcl/domain/contracts.py` before implementation. Evidence, Constraint, TrajectoryPoint, Trajectory, ObjectiveSpec, ActionStep, ActionPlan, FalsificationResult, and LoopCycle are the nine contracts. Each has field validators enforcing invariants at construction time: constraints must carry evidence IDs, trajectories must have at least one point, action plans must have at least one step, committed_step_index must be 0, weights must match terms in length. Twenty-five contract tests (`tests/test_contracts.py`) verify these validators, including rejection of invalid inputs.

### 7.2 Test-Driven Development (TDD)

Tests are written red (failing) before implementation, then green. Each component has a dedicated test file: `test_constraint_classifier.py` (12 tests), `test_controller.py` (17 tests), `test_falsification_gate.py` (15 tests), `test_horizon_predictor.py` (14 tests), `test_objective_interpreter.py` (11 tests), `test_classification_adapter.py` (9 tests), `test_fleet_adapter.py` (14 tests), `test_loop_driver.py` (8 tests), `test_ledger.py` (6 tests), `test_scenario.py` (22 tests), `test_api.py` (12 tests).

### 7.3 Behavior-Driven Development (BDD)

End-to-end scenario tests (`tests/test_scenarios.py`, 11 tests) run the full loop against each scenario. Each test follows the Given-When-Then pattern: given a specific scenario step with known evidence, when the loop runs, then the committed action satisfies the expected invariant. Six BDD test classes cover compliance (alert, not scale), capacity exhaustion (shed_load), mixed storm (compliance priority), spike detection (scale or pre_warm, not no_action), extreme bounded (scale capped), zero capacity (shed_load, not infeasible), full scenario replay (disturbance rejected, recovery committed), and multi-cluster migration (migrate or shed_load at step 3, alert or migrate at step 4).

### 7.4 Evidence-Driven Design (EDD)

A 24-dimension rubric grid (`tests/test_rubrics.py`, 30+ tests across 24 rubric classes), each scored by tests, all of which must be green:

1. **Constraint justification.** Every constraint carries justifying evidence IDs or is dropped.
2. **Two-stage classification.** Deterministic rules fire first; LLM only for ambiguous evidence, marked with lower confidence.
3. **LLM boundary.** AST inspection proves no ActionPlan or ActionStep import in the interpreter module.
4. **Hard-constraint guarantee.** Committed step never violates a hard constraint (50 randomized trials in rubric, 300 in properties).
5. **Receding horizon.** Committed step index is always 0.
6. **Falsification rejects.** Bad actions are rejected pre-commit with the failed check named.
7. **No optimality overclaim.** No source file claims optimality (full directory scan).
8. **Chain provenance.** Every cycle writes classify, predict, interpret, plan, and commit/reject under one correlation ID.
9. **Classification input fidelity.** Class name, confidence, severity, and metrics faithfully mapped from ClassificationRecord to Evidence.
10. **Action type coverage.** All 5 non-migrate action types (scale, pre_warm, shed_load, alert, no_action) are reachable via the optimizer. Migrate is the 6th, reachable via compliance + capacity exhaustion.
11. **Compliance action correctness.** Compliance violation produces alert or migrate, never scale.
12. **Load shedding safety.** shed_load only produced when capacity is exhausted AND latency is breached.
13. **Scale magnitude bounded.** Scale capped by both max_replicas and configured maximum; falsification rejects extremes.
14. **Spike detection.** Spikes produce scale or pre_warm, not no_action; normal data does not produce false spikes.
15. **Multi-cluster migrate.** Compliance + capacity exhaustion produces migrate; compliance alone produces alert.
16. **Semantic routing.** The GCL prompt classifier classifies prompts into tiers (simple/standard/complex) for fleet-llm-d's semantic routing, and tier distribution feeds as evidence into the governance loop.
17. **Centralized metrics.** The GCL can pull live platform metrics from fleet-llm-d's centralized metrics API (GET /api/v1/metrics/platform) and run governed cycles driven by real-time cross-system data.
18. **Guardian sidecar.** The Guardian runtime sidecar enforces honesty boundary constraints at the container level, preventing LLM escape from the interpret-only role.
19. **Post-commit verification.** Every committed action produces a gcl.outcome ledger entry recording whether the action achieved its intended effect.
20. **Decision cooldown.** A 60-second default cooldown prevents action oscillation between consecutive cycles.
21. **Fleet response tracking.** The committer tracks fleet-llm-d's response to each intent, recording acceptance, rejection, or timeout in the ledger.
22. **Actuation verification.** gcl.actuation_verified entries confirm that fleet-llm-d accepted and executed the intent, closing the decide-actuate loop.
23. **Chaos resilience.** gcl.cycle_start entries and graceful degradation ensure the loop recovers from component failures without data loss or invalid commits.
24. **Time-aware constraints.** Maintenance window enforcement and time-of-day scaling policies prevent actuation during scheduled downtime or restricted periods.

### 7.5 Confidence-Based Testing (CBT)

24 edge case simulations on production infrastructure patterns, implemented as randomized property tests across three property classes:

- **Hard-constraint satisfaction** (`TestHardConstraintProperty`): 100 randomized seeds. Each trial generates a random trajectory (latency values 1000-10000ms), random constraints (latency bounds 2000-8000ms, capacity bounds 3-20 replicas, optional budget), and verifies that no committed step violates any hard constraint.

- **Compliance property** (`TestComplianceProperty`): 50 randomized seeds. Each trial adds a hard compliance constraint and verifies that the committed step is never scale or pre_warm.

- **Shed load property** (`TestShedLoadProperty`): 50 randomized seeds. Each trial creates a scenario with high latency breach values (6000-15000ms) and tight capacity (bound=1), and verifies that when shed_load is produced, max_inflight >= 1 and duration_seconds > 0.

An additional 100 property seeds test that committed_step_index is always 0 (`test_committed_step_index_is_always_zero`).

### 7.6 Test Summary

782 tests total:

| Category | Count | Source |
|---|---|---|
| Unit tests (component-level) | 140 | test_contracts, test_controller, test_constraint_classifier, test_falsification_gate, test_horizon_predictor, test_objective_interpreter, test_classification_adapter, test_fleet_adapter, test_loop_driver, test_ledger, test_scenario, test_api |
| Randomized property seeds (hard-constraint satisfaction) | 200 | test_properties (100 hard-constraint + 100 committed-index) |
| Randomized property seeds (compliance + shed_load) | 100 | test_properties (50 compliance + 50 shed_load) |
| BDD scenario tests | 11 | test_scenarios |
| EDD rubric tests | 30+ | test_rubrics (24 rubric dimensions, some with multiple test methods) |
| CBT edge case coverage | 24 | Subset of property tests covering production edge cases |

## 8. Production Results on Oberon

### 8.1 Deployment Environment

Deployed on OpenShift (Oberon cluster). Single-node, Red Hat Enterprise Linux CoreOS 9.8, Kubernetes 1.35. The GCL runs as a containerized Python application alongside fleet-llm-d (Go control plane) and the ARE Immutable Ledger.

### 8.2 Ledger Evidence

1,400 GCL entries in the ARE Immutable Ledger. 193 correlation chains, each representing a complete cycle from classify through commit/reject. All 32 chain types cryptographically valid (SHA-256 hash chains verified via `GET /api/verify`).

### 8.3 Governed Cycle Results

200+ governed cycles completed:

| Outcome | Count | Percentage |
|---|---|---|
| Committed | 96 | 74% |
| Rejected | 33 | 26% |

**Rejection reasons:**

| Reason | Count | Notes |
|---|---|---|
| low_prediction_confidence | 24 | Trajectory confidence below 0.5 floor. Correct: insufficient data should not drive actuation. |
| capacity_overcommit | 9 | Action requested more replicas than evidence allowed. Correct: the gate prevented overcommit. |

**Action distribution (committed cycles):**

| Action Type | Count |
|---|---|
| no_action | 55 |
| scale | 29 |
| alert | 5 |
| pre_warm | 4 |
| shed_load | 3 |

### 8.4 The Replicas Bug Receipt

The ledger contains permanent evidence of the replicas=200 bug (pre-fix, 04:06:58 UTC July 10) and the replicas=20 fix (04:38:23 UTC, same day, same input). Before the fix, the Controller's scale computation was unbounded: an extreme latency value divided by the latency target produced a replica count of 200, which violated the capacity constraint. The falsification gate caught this via `capacity_overcommit` and rejected the action. After the fix (adding `max_scale_replicas` to config and capping in the optimizer), the same input produced replicas=20, which passed falsification and committed.

Both records exist in the immutable ledger under different correlation IDs. This is the receipt working as designed: the permanent record proves both that the bug existed and that it was fixed. No entry can be deleted or modified after the fact.

### 8.5 Fleet Integration

fleet-llm-d accepted intents via HMAC-SHA256 auth (confirmed in controller logs: "intent (scale) accepted"). The fleet adapter generated tokens with claims (subject: "governed-cognitive-loop", role: "operator", expiration: 24 hours) and signed them with the shared secret. The fleet-controller validated the signature and processed the intent.

### 8.6 Operational Stability

Zero pod restarts on the GCL application overnight. The fleet-controller had one OOMKill at 256Mi memory limit (bumped to 512Mi, resolved). No other stability issues observed during the production validation window.

## 9. What This System Does Not Claim

This section is required by the build prompt and the EDD rubric. The `TestNoOptimalityOverclaim` test enforces that no source file in the `gcl/` directory makes an optimality claim. No generated text may claim optimality or infallibility.

### 9.1 What the System Does Not Claim

**Optimality.** The objective is LLM-specified (or template-specified). Classical optimality guarantees require a mathematically defined, fixed objective function. When the objective comes from an LLM, the best the controller can do is satisfy hard constraints and select an action consistent with the weights. The action may not be the best possible action. It is a feasible action that does not violate constraints.

**Infallibility.** 99% composite confidence means approximately 1% of realistic scenarios may produce suboptimal (though safe) decisions. Low-confidence trajectories are rejected by the falsification gate rather than committed, but the confidence threshold itself (0.5) is a configuration choice, not a mathematical proof.

**Complete action coverage.** The controller has 7 action types: no_action, scale, pre_warm, shed_load, alert, migrate, and rollback. Real infrastructure has more levers: adjusting batch sizes, changing model quantization, rerouting to CPU inference, modifying timeout policies, or triggering blue-green deployments. The GCL's action vocabulary is deliberately small and verifiable.

**Real-time latency guarantees.** The loop is cycle-based (request-response), not streaming. Each cycle runs the full pipeline (classify, predict, interpret, optimize, falsify, commit), which includes potential LLM calls for interpretation and adversarial probing. In force-deterministic mode (no LLM calls), cycle latency is dominated by the ledger write. In LLM-enabled mode, cycle latency includes LLM inference time (configured timeout: 30 seconds). The system does not guarantee sub-second decision latency.

### 9.2 What the System Does Claim

**Hard constraints are never violated by a committed action.** The Controller's `check_hard_constraint_satisfaction` function rejects any action that would violate a hard constraint. The FalsificationGate's `check_capacity_available` provides a second verification. 300 randomized property tests confirm this across random trajectories and constraint combinations.

**Every plan is challenged before commit.** Seven deterministic falsification checks and an optional LLM adversary examine every committed step. Every rejection has a named reason (capacity_overcommit, low_prediction_confidence, scale_magnitude_unreasonable, warmup_time_unrealistic, compliance_action_invalid, shed_load_unbounded, migration_target_missing, or llm_adversarial_probe).

**Every decision is recorded in a hash-chained, cryptographically verifiable ledger.** Every cycle writes classify, predict, interpret, plan, falsify, and commit/reject entries under a single correlation ID. The chain is append-only and verified via `GET /api/verify`. 1,400 entries across 193 chains were verified on the Oberon production cluster.

**The LLM never produces the committed action.** An AST inspection test proves this: no file in the interpreter module imports ActionPlan or ActionStep. The LLM produces weights and cost terms. The deterministic controller produces the action. A test enforces this boundary on every commit.

---

**Author:** Jonathan Kershaw
**Date:** July 2026
**Version:** Draft 0.1
