# MAPPING: Story Beats to Real Cycle Data

Every beat maps to a component field or code path. Scenario and standalone data remain component evidence, not proof of live ecosystem integration.

## Layer 0: The Hook (FalsificationGate)

| Beat | Real Cycle Field | Code Path | Drawn As |
|------|-----------------|-----------|----------|
| Proposed action | `LoopCycle.action_plan.steps[0]` | `gcl/controller/controller.py:optimize()` | FalsificationCard left panel |
| Rejection verdict | `LoopCycle.falsification.verdict == "fails"` | `gcl/falsification/gate.py:falsify()` | FalsificationCard status badge |
| Failed check named | `LoopCycle.falsification.failed_check` | `gcl/falsification/checks.py` | FalsificationCard right panel |
| Rejection reasoning | `LoopCycle.falsification.reasoning` | `gcl/falsification/checks.py` | FalsificationCard detail text |
| Action held | `LoopCycle.committed == False` | `gcl/committer/committer.py:commit()` | FalsificationCard "REJECTED" label |

## Layer 1: The Evidence (ConstraintClassifier)

| Beat | Real Cycle Field | Code Path | Drawn As |
|------|-----------------|-----------|----------|
| Evidence-grounded constraint | `LoopCycle.constraints_snapshot[i].justification_evidence_ids` | `gcl/classifier/rules.py:evaluate()` | ConstraintBadge with evidence count |
| Constraint type and bound | `Constraint.type`, `Constraint.bound` | `config/defaults/constraints.yaml` | ConstraintBadge type pill and bound |
| Hard vs soft | `Constraint.hard` | `gcl/classifier/rules.py` | ConstraintBadge HARD/SOFT tag |
| Deterministic source | `Constraint.source == "deterministic"` | `gcl/classifier/classifier.py:classify()` | ConstraintBadge source label |
| Dropped constraint | Constraint with empty `justification_evidence_ids` | `gcl/domain/contracts.py:must_have_evidence()` | Ghost card (dropped) |
| Confidence score | `Constraint.confidence` | `gcl/classifier/rules.py` | ConstraintBadge confidence percentage |

## Layer 2: The Lookahead (HorizonPredictor + Controller)

| Beat | Real Cycle Field | Code Path | Drawn As |
|------|-----------------|-----------|----------|
| Predicted trajectory | `LoopCycle.trajectory.points[i].value` | `gcl/predictor/predictor.py:predict()` | HorizonPlot dashed blue line |
| Confidence envelope | `TrajectoryPoint.lower`, `TrajectoryPoint.upper` | `gcl/predictor/predictor.py` lines 26-31 | HorizonPlot shaded blue area |
| Trajectory confidence | `LoopCycle.trajectory.confidence` | `gcl/predictor/slo_seed.py:linear_regression()` | MetricCard percentage |
| Constraint boundaries | `Constraint.bound` from `constraints_snapshot` | `gcl/classifier/rules.py` | HorizonPlot horizontal bands (red/yellow) |
| Selected first step | `action_plan.committed_step_index == 0` | `gcl/controller/controller.py` validator | HorizonPlot green circle + "SELECTED" |
| Horizon redraw on disturbance | New `trajectory.points` after spike | `gcl/predictor/predictor.py:predict()` | HorizonPlot animated pathLength redraw |
| Receding horizon discipline | Only `committed_step_index == 0` accepted | `gcl/domain/contracts.py:committed_index_is_zero()` | Single green marker, no multi-step commit |

## Layer 3: The Floor (ObjectiveInterpreter + Controller Boundary)

| Beat | Real Cycle Field | Code Path | Drawn As |
|------|-----------------|-----------|----------|
| LLM sets objective | `LoopCycle.objective.terms`, `.weights`, `.rationale` | `gcl/interpreter/interpreter.py:interpret()` | Boundary diagram left box (purple) |
| Controller computes action | `LoopCycle.action_plan.steps[0]` | `gcl/controller/controller.py:optimize()` | Boundary diagram right box (green) |
| Honesty boundary | No `ActionPlan` or `ActionStep` in interpreter module | `gcl/interpreter/` (AST test) | Arrow labeled "objective only" |
| Full ledger chain | `GET /api/v1/cycles/{id}/chain` entries | `gcl/loop/ledger.py:write_entry()` | LedgerChain vertical timeline |
| Chain stages | `gcl.classify`, `gcl.predict`, `gcl.interpret`, `gcl.plan`, `gcl.falsify`, `gcl.decision_package.proposed`/`gcl.reject` | `gcl/loop/driver.py:run_cycle()` | LedgerChain entry dots |
| Correlation ID links chain | `LoopCycle.correlation_id` matches all entries | `gcl/loop/driver.py` | LedgerChain shared correlation |
| No optimality claim | `objective.rationale` text | `gcl/interpreter/templates.py` | Text contains no "optimal" |
