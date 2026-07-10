# Walkthrough: SA Navigation Map

This is a navigation map, not a linear script. Each layer is independently runnable. You can jump to any layer, stop after any layer, and the demo resets cleanly.

**Controls:** Arrow keys navigate between layers. Enter begins. The Reset button in the header clears all state.

---

## Layer 0: The Hook (FalsificationGate)

**What is on screen:** A single cycle where the proposed action is rejected by the FalsificationGate. The FalsificationCard shows the proposed action (type, parameters), the specific check that failed, and the reasoning.

**Thread:** It tried to disprove its own plan against the evidence.

**Question provoked:** What is it checking against?

**Humor beat:** "The colleague who reads the email back before hitting send."

**Turn:** A human does this on a good day. This one does it every cycle.

**How to descend:** Click Layer 1 or press the right arrow. The next layer answers: what are these constraints it checked against?

**How to stop cleanly:** This layer stands alone. The beat is complete: it tries to prove its own plan wrong before acting.

**Technical question this layer invites:** Why not just use reactive thresholds?
**Answer:** Reactive thresholds fire after the breach. Falsification fires before commit, on the proposed action, against the current evidence. It catches assumptions the plan makes that the evidence contradicts, not conditions the system has already hit.

---

## Layer 1: The Evidence (ConstraintClassifier)

**What is on screen:** A list of ConstraintBadges showing each constraint derived from evidence. Each badge shows the type, bound, hard/soft flag, confidence, source (deterministic or LLM), and the number of justifying evidence items. One "dropped" ghost card illustrates the evidence-first principle.

**Thread:** Constraints come from evidence, so they move as the situation moves.

**Question provoked:** How does it plan under those constraints?

**Humor beat:** "Unlike the manual that still says to do the thing that stopped working two years ago."

**Turn:** These constraints carry the evidence that justifies them.

**How to descend:** Click Layer 2 or right arrow. The next layer shows the horizon plan under these constraints.

**How to stop cleanly:** Layers 0 and 1 together show: it challenges its plan (0) against evidence-grounded constraints (1). Complete on its own.

**Technical question:** Why two-stage classification (deterministic then LLM)?
**Answer:** Deterministic rules handle the common, well-understood cases with high confidence. The LLM is only consulted for ambiguous or novel evidence, and its output is marked with lower confidence. This keeps the classification auditable and limits LLM influence to where it adds value.

---

## Layer 2: The Lookahead (HorizonPredictor + Controller) -- Hero Layer

**What is on screen:** The HorizonPlot, the hero visualization. It builds across multiple cycles: measured history accumulates on the left, the predicted trajectory extends on the right as a dashed blue line with a confidence envelope. Constraint boundaries are shaded. The committed step is a green circle. When the disturbance arrives, the trajectory redraws with a spring animation.

**Thread:** It committed only one step and re-planned.

**Question provoked:** Who sets the goal it is optimizing?

**Humor beat:** "Unlike the person who booked the whole itinerary and refused to change it after the flight was cancelled."

**Turn:** It commits only the next step and re-checks every cycle.

**How to descend:** Click Layer 3 or right arrow. The next layer reveals the honesty boundary: the LLM sets the objective, but the controller computes the action.

**How to stop cleanly:** Layers 0-2 together show the full operational loop without the LLM boundary discussion. Complete for a technical audience that wants the mechanics.

**Technical question:** Where is the optimality guarantee?
**Answer:** There is none, and the system does not claim one. The objective is LLM-specified, so classical optimality guarantees do not hold. The guarantee is: hard constraints are satisfied, the plan survived falsification, and only one step is committed per cycle. That is the floor, not the ceiling.

---

## Layer 3: The Floor (ObjectiveInterpreter + Controller Boundary)

**What is on screen:** Two panels. Left: the honesty boundary diagram showing the ObjectiveInterpreter (purple, LLM) feeding an objective into the Controller (green, deterministic), with a clear label that only the objective crosses the boundary. Right: the LedgerChain showing every entry in the cycle's audit trail, expandable to see the full JSON.

**Thread:** The creative part never touches the safety-critical lever, and the receipt is on record.

**Question provoked:** So can I let it run on real decisions?

**Humor beat:** "More discipline than most org charts manage."

**Turn:** It separates creative framing from guaranteed execution and keeps the receipt.

**How to descend:** Click Close or right arrow.

**How to stop cleanly:** All four layers together are the complete descent. Each one built on the thread planted by the previous.

**Technical question:** Why is the LLM allowed near this at all?
**Answer:** The LLM interprets context into an objective (what to optimize for) and predicts disturbances. It never computes the control action and never performs constraint satisfaction. A test proves this by AST inspection: the interpreter module has no import of ActionPlan or ActionStep. The LLM adds judgment about the goal, which a static template cannot. But judgment about the goal is separated from execution of the action.

---

## The Close

**What is on screen:** The belief sentence in large text, four summary tags (Falsification, Evidence-grounded, Receding horizon, Honesty boundary), and the honesty disclaimer.

**No new API calls.** The close is a summary, not a demonstration.
