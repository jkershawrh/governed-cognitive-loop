# Build Prompt: Governed Cognitive Loop

**Working name:** `governed-cognitive-loop` (LLM-MPC with evidence-based constraint classification and hypothesis falsification before commit)
**Hand-off target:** Claude Code CLI
**Discipline:** read-existing-project-first, incremental milestones, preflight before work, CDD then TDD then BDD then EDD with red/green rubric grids, verify.sh exits 0 on success.
**Formatting rule for all generated docs, comments, and commit messages:** no em-dashes anywhere. Use commas, colons, periods, and parentheses.

---

## Assumptions (adjust before starting)

1. New repository named `governed-cognitive-loop`. It is substrate-agnostic at its core and ships with one adapter that actuates against `fleet-llm-d` through `deepfield-fleet`'s intent path.
2. Python 3.12+, FastAPI, Pydantic v2, pytest, httpx, numpy for the deterministic controller math. Matches the `deepfield-fleet` lineage.
3. The ARE Immutable Ledger is reachable over HTTP with the same entry schema used elsewhere in the stack.
4. An LLM endpoint (Granite on Xeon or Gaudi, or a MaaS endpoint) is available for the objective interpreter and the optional adversarial probe. Every LLM call must have a deterministic fallback so the loop runs without an LLM for testing.

---

## Mission

Build one control cycle with three named organs, each owning a distinct stage. The loop classifies which constraints apply from evidence, plans an action over a horizon under those constraints, tries to disprove that action before committing it, commits only what survives, then re-measures and re-plans.

```
Signals -> Classify constraints (from evidence)
        -> Predict horizon + Interpret objective (LLM) + Optimize under constraints (deterministic)
        -> Falsify the committed action (disconfirmation, pre-commit)
        -> Commit the survivor (first step only)
        -> Re-measure -> repeat
```

### The honesty boundary (this is the heart of the design, do not blur it)

- The LLM **interprets** context into an objective and constraint weighting, and **predicts** disturbances. That is all.
- The LLM **never** computes the committed control action and **never** performs constraint satisfaction. A deterministic controller owns optimization and owns the hard-constraint guarantee.
- Do not claim optimality. Because the objective is LLM-specified, classical optimality guarantees do not hold. The guarantee this system provides is hard-constraint satisfaction and falsification-gated commit, not optimality. State this in the code and the docs.
- Falsification seeks disconfirmation. It tries to break the proposed action, not to confirm it.

---

## Before You Write Any Code

1. Read `deepfield-fleet`, especially `app/microagents/slo_forecaster.py` (reuse as the horizon predictor seed), `app/intents/emitter.py` and `app/domain/fleet_intents.py` (the actuation path), and `app/macroagents/consequence_scoper.py`.
2. Read `are-immutable-ledger` for the entry and correlation-id schema.
3. Confirm the LLM endpoint contract and write a deterministic template fallback for every LLM call site before wiring the real model.
4. Write `docs/READFIRST.md` with findings and assumptions. Flag anything that would change the contracts.

---

## Architecture

### Components and their single responsibilities

- `ConstraintClassifier`. Evidence to a list of typed constraints, each with the evidence that justifies it. Two-stage and evidence-first: deterministic rules resolve the common cases; the LLM is consulted only for ambiguous or novel evidence, and its output is marked `source=llm` and carries lower confidence. A constraint with no justifying evidence is invalid and must be dropped.
- `HorizonPredictor`. Current and recent state to a predicted trajectory over a horizon, with confidence. Seed from the SLO forecaster and generalize the interface so other signal types can plug in.
- `ObjectiveInterpreter` (the LLM slot). Context plus classified constraints to an `ObjectiveSpec`: cost terms and weights, and a partition of constraints into hard and soft. This never emits an action. Deterministic template fallback required.
- `Controller` (deterministic). Predicted trajectory plus `ObjectiveSpec` plus hard constraints to a candidate action plan over the horizon, computed with real math (numpy). Receding horizon: it returns the full plan but marks only the first step as committed. It must satisfy every hard constraint or return infeasible; it never emits an action that violates a hard constraint.
- `FalsificationGate` (pre-commit). Treats the committed first step as the hypothesis "this action produces the intended outcome under the predicted conditions." Runs disconfirmation checks: deterministic checks first (does the plan assume capacity that the evidence says is unavailable, does it assume a warm-up time the pool is not meeting, does it depend on a prediction whose confidence is below threshold), then an optional LLM adversarial probe that argues for failure. Returns `survives` or `fails`, the failed check, and the reasoning.
- `Committer`. On `survives`, actuate the first step (through the adapter) and record the prediction and action to the ledger. On `fails`, reject or request a revision, and record the rejection and its reasoning to the ledger.
- `LoopDriver`. Runs the cycle, advances the receding horizon, and re-measures each iteration.
- `FleetAdapter`. Maps a committed action to a `deepfield-fleet` intent (PreWarm, Scale, ShedLoad) and emits it. The core loop has no knowledge of the fleet; only the adapter does.

### Data model (CDD contracts, define first)

- `Constraint(id, type, bound, hard, justification_evidence_ids, confidence, source)` where type is one of capacity, priority, compliance, residency, budget, latency, custom.
- `Trajectory(points, horizon_steps, confidence, generated_at)`
- `ObjectiveSpec(terms, weights, hard_constraint_ids, soft_constraint_ids, rationale)`
- `ActionPlan(steps, committed_step_index, horizon_steps)`
- `FalsificationResult(action_id, verdict, failed_check, reasoning, evidence_ids)`
- `LoopCycle(cycle_id, constraints_snapshot, trajectory, objective, action_plan, falsification, committed, correlation_id)`

### Ledger chain per cycle

Each cycle writes a chain under one correlation id: the prediction and the classified constraints snapshot, the interpreted objective, the proposed action, the falsification result (survived or rejected with reasoning), and the outcome once observed. This is the receipt: what the system saw, what it planned, what it tried to disprove, what it committed, and whether it held.

---

## Milestones

Each milestone lands CDD contracts, then TDD tests red first, then BDD scenario tests, then an EDD rubric grid scored by tests. verify.sh must pass for the milestone before it is done.

### M0 Foundation
Preflight, READFIRST.md, all contracts, config (horizon length, confidence thresholds, disconfirmation check parameters), and deterministic fallbacks stubbed. No logic.

### M1 ConstraintClassifier
Deterministic-first classification with the LLM as the ambiguous-case second stage. Every emitted constraint carries justifying evidence ids or is dropped. TDD across clear, ambiguous, conflicting, and empty evidence.

### M2 HorizonPredictor
Trajectory over a horizon with confidence, seeded from the SLO forecaster and generalized. TDD across trending, flat, noisy, and insufficient-data inputs.

### M3 ObjectiveInterpreter (LLM slot)
Context and constraints to an `ObjectiveSpec`. Hard boundary test: this component has no code path that returns an action, and a test asserts that. Deterministic template fallback produces a valid `ObjectiveSpec` with the LLM disabled.

### M4 Controller (deterministic)
Optimizes over the horizon under hard constraints, commits only the first step. Tests assert: no hard constraint is ever violated by the committed step, infeasible inputs return infeasible rather than a violating action, and only the first step is marked committed.

### M5 FalsificationGate
Pre-commit disconfirmation. Deterministic checks first, optional LLM adversarial probe second. Tests assert a knowingly bad action (for example one assuming a cold-start time the evidence contradicts) is rejected with the correct failed check named, and that a sound action survives.

### M6 LoopDriver and ledger chain
The full cycle runs end to end, advances the receding horizon, re-measures, and writes a complete chain per cycle. Tests assert a rejected action never actuates and still produces a ledger record of the rejection.

### M7 FleetAdapter and API
Committed actions map to `deepfield-fleet` intents and emit. API exposes cycle inspection so a viewer can read the horizon, the constraints, the committed action, and any rejected branch. Integration test against a live or fixtured fleet endpoint.

### M8 (optional, research-room visual)
Horizon plot: measured history left of a now line, predicted trajectory right of it, hard-constraint boundaries shaded, the committed step dropped, and a rejected falsification branch drawn distinctly. This is the visualization that makes the receding horizon and the falsification visible. Treat it as a research-audience asset, not a partner-room requirement.

---

## EDD rubric grid (green is required to pass)

| Dimension | Red | Yellow | Green |
|-----------|-----|--------|-------|
| Constraint justification | Emits constraint with no evidence | Weak or partial evidence link | Every constraint carries justifying evidence ids or is dropped |
| Two-stage classification | LLM does all classification | LLM used where rules would do | Deterministic first, LLM only for ambiguous, marked and lower-confidence |
| LLM boundary | LLM output reaches the control action | LLM influences the action indirectly | LLM only sets objective and predicts; a test proves no action path from the LLM |
| Hard-constraint guarantee | Committed step violates a hard constraint | Violates only in edge inputs | Committed step never violates a hard constraint; infeasible returned instead |
| Receding horizon | Commits multiple steps | Commits first plus lookahead side effects | Commits only the first step, re-plans each cycle |
| Falsification rejects | Bad action commits | Rejects late, after partial actuation | Bad action rejected pre-commit with the failed check named |
| No optimality overclaim | Docs or logs claim optimality | Ambiguous language | States the guarantee is constraint satisfaction and falsification, not optimality |
| Chain provenance | Cycle with no ledger chain | Chain missing the falsification leg | Every cycle writes classify, plan, falsify, commit, and outcome under one correlation id |

---

## preflight.sh

Checks: Python version, venv, dependencies including numpy, ledger reachable, LLM endpoint reachable or fallback flag set, `slo_forecaster` and the fleet intent models importable, and config parses with a valid horizon and thresholds. Exits non-zero with a clear message on any failure.

## verify.sh

Runs, in order: preflight, `pytest -q` (unit, BDD, and EDD rubric tests), the LLM-boundary assertion test, a hard-constraint-satisfaction property test over randomized feasible and infeasible inputs, a falsification test proving a known-bad action is rejected pre-commit, and an end-to-end cycle against a fixtured fleet and seeded ledger that writes a complete chain. Prints a one-line pass summary and exits 0 only if every check passes.

## Definition of Done

verify.sh exits 0. The loop runs classify, predict, interpret, optimize, falsify, commit, and re-measure. The LLM never produces the committed action and a test proves it. Hard constraints are never violated by a committed step. A known-bad action is rejected before commit with its failed check named. Every cycle produces a complete, reconstructable ledger chain. No optimality is claimed anywhere. No em-dashes in any generated text.
