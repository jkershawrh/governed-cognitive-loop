# Story Arc: Governed Cognitive Loop

**Belief sentence:** It makes hard calls the way a careful expert does, and it never skips the step where it tries to prove itself wrong.

**Honesty constraint:** This system does not claim optimality, perfection, execution, or production readiness. Local evidence covers decision-package construction and falsification, not infrastructure outcomes.

---

## Layer 0. The Hook: It tries to prove its own plan wrong before acting.

**Human truth:** The difference between a novice and an expert is not speed. The novice acts on the first plausible plan. The expert pauses and asks what would make this the wrong call, and the pause is the thing you trust.

**Live behavior:** The loop proposes a scaling action and the `FalsificationGate` (`gcl/falsification/gate.py`) engages before commit. It runs deterministic disconfirmation checks against evidence: does the action assume capacity that evidence says is unavailable? Does it depend on a prediction whose confidence is too low? The action is rejected because the evidence contradicts an assumption.

**Drawn:** The proposed action (type, parameters), the specific check that failed (named), and the action being held rather than executed. The FalsificationCard renders the verdict, the failed check, and the reasoning.

**Thread planted:** It tried to disprove its own plan against something.

**Question provoked:** What is it checking the plan against?

**Humor beat:** It is the colleague who reads the email back before hitting send and catches the mistake, unlike the one who fires first and apologizes later.

**Turn:** A human does this on a good day. This one does it every cycle and never talks itself out of the check because it is late or sure of itself.

---

## Layer 1. The Evidence: It reads the situation, not a stale rulebook.

**Human truth:** A good expert derives the real constraints from what is in front of them. The junior applies the manual. The expert sees that today is different.

**Live behavior:** The `ConstraintClassifier` (`gcl/classifier/classifier.py`) derives constraints from evidence, each with justifying evidence IDs. Deterministic rules handle the common cases first; the LLM is consulted only for ambiguous or novel evidence, and its output is marked `source=llm` with lower confidence. A constraint with no justifying evidence is invalid and gets dropped.

**Drawn:** Each active constraint as a ConstraintBadge with type, bound, hard/soft flag, source, confidence, and evidence count. Constraint boundaries appear on the horizon plot as shaded regions.

**Thread planted:** Constraints came from evidence, so they move as the situation moves.

**Question provoked:** How does it plan under those constraints, and how far ahead does it look?

**Humor beat:** Unlike the manual that still says to do the thing that stopped working two years ago, it notices when the situation changed.

**Turn:** A human's rules are often habit and stale policy. These constraints carry the evidence that justifies them, so you can check why each one exists.

---

## Layer 2. The Lookahead: Think ahead, commit one step, re-check.

**Human truth:** A careful expert thinks several moves ahead but does not lock in the whole plan, because the situation will change. They take the next step and reassess. The overcommitter executes a five-step plan even as the facts move.

**Live behavior:** The `HorizonPredictor` (`gcl/predictor/predictor.py`) produces a trajectory over the planning horizon with confidence from linear regression. The `Controller` (`gcl/controller/controller.py`) computes candidate actions under hard constraints using numpy, but selects only the first step (`committed_step_index == 0`). Each cycle re-measures and re-plans from fresh data. A disturbance arrives mid-scenario, the trajectory is redrawn, and the plan adjusts.

**Drawn:** The HorizonPlot as the centerpiece. Measured history left of a "NOW" line, predicted trajectory right of it (dashed blue), confidence envelope (shaded blue area), hard-constraint boundaries (shaded red), the selected first step (green circle with "SELECTED" label), and the trajectory visibly redrawn when the disturbance lands (animated pathLength).

**Thread planted:** It committed only one step and re-planned, and the goal it optimized came from somewhere.

**Question provoked:** Who sets the goal it is optimizing, and can I trust that part?

**Humor beat:** Unlike the person who booked the whole itinerary and refused to change it after the flight was cancelled, it re-plans when reality moves.

**Turn:** A human overcommits to sunk-cost plans. This one commits only the next step and re-checks every cycle, so it cannot ride a dead plan into a wall.

---

## Layer 3. The Floor: The creative part never touches the safety-critical lever.

**Human truth:** You want judgment about the goal to be explainable, and you do not want the fast, fallible part of the mind holding the lever that cannot be pulled back. Frame the problem with intuition, execute it with discipline.

**Live behavior:** The `ObjectiveInterpreter` (`gcl/interpreter/interpreter.py`), backed by the LLM or a deterministic template, reads context and produces an `ObjectiveSpec` (cost terms, weights, rationale). The deterministic `Controller` owns candidate computation and constraint checks. The interpreter has no code path that returns an action (verified by AST inspection in tests). A surviving consequential candidate is encoded in a signed `DecisionPackage` and proposed with `execution_verified=false`.

**Drawn:** The honesty boundary as two connected boxes: "ObjectiveInterpreter (LLM)" with purple border feeding "objective only" into "Controller (deterministic)" with green border. The LedgerChain renders decision entries ending in `gcl.decision_package.proposed` or `gcl.reject`.

**Thread planted:** The creative part never touches the safety-critical lever, and the whole decision is on the record.

**Question provoked:** So can I let it run on real decisions?

**Humor beat:** It lets the imaginative part brainstorm the goal but keeps it nowhere near the launch button, which is more discipline than most org charts manage.

**Turn:** A human's intuition and execution live in the same fallible head, and this system claims no optimality either. It separates creative framing from deterministic candidate checks and emits a reviewable signed proposal. ARE and fleet remain responsible for authorization, receipts, and observed execution.

---

## The Close

It makes hard calls the way a careful expert does: reads the real constraints from evidence, thinks ahead but commits only the next step, and tries to prove its own plan wrong before acting. Except it never skips the self-challenge, never rides a dead plan, never lets the creative part touch the safety-critical lever, and keeps the receipt every time. It does not promise to be right. It promises to stay inside the limits and to have tried to prove itself wrong first. That is the sentence they repeat.
