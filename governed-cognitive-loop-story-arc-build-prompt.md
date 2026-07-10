# Build Prompt: Governed Cognitive Loop — On-Ramp Story Arc, Demo, Walkthrough, and Lab

**Hand-off target:** Claude Code CLI
**Depends on:** the `governed-cognitive-loop` service (built separately). This build produces the narrative and demo layer over that live system. It does not mock the system; it drives it and it draws it.
**Discipline:** read-existing-project-first, ground every beat in a real system behavior, make the invisible visible, build the arc as one navigable spine, verify.sh exits 0 on success.
**Formatting rule for all generated text (story, deck, walkthrough, lab, comments, commits):** no em-dashes anywhere. Use commas, colons, periods, and parentheses.

---

## Read this first: how this differs from the promotion-line story build

This loop is not a broad 101 piece by default. Its intellectual payoff is invisible on screen unless it is drawn, and its center of gravity is a technical or research room. Two consequences shape everything below.

1. **The visualization is the demo, not a garnish.** On the promotion line, earning and demotion are visible events you can narrate. Here, the horizon, the constraint boundaries, and the rejected plan are internal machinery that render as nothing unless you draw them. A text-only or log-only demo of this loop fails. The horizon plot is the hero deliverable.
2. **Pick the room, because it changes the build.** Set the target room parameter. `research_full_loop` builds the complete descent for a technical or research audience. `partner_extracted_beat` builds only the falsification-before-commit surface for a mixed partner room, because forcing the full three-organ loop on a non-technical budget room is a known mistake. Do not build the full loop for a partner room and hope it lands.

---

## Parameters (set before starting)

1. **Target room.** Default: `research_full_loop`. Alternative: `partner_extracted_beat` (builds only Layer 0 and the close, dropping the constraint and horizon depth, and pointing the falsification beat at a domain with felt stakes).
2. **The decision domain.** The loop in the story is a careful expert making a hard call in a specific domain. Default: the inference-fleet control the `governed-cognitive-loop` service already drives (scale, pre-warm, shed under an event). If your room is a specific vertical, set the domain there, but keep the cycle structure identical to the service's real behavior so the story shows the real system.
3. **Characterization level.** Default: light. The loop is framed as "a careful expert" narrated over the real system, not a named character. Gimmick undercuts a rigor demo.

---

## Mission

Build the on-ramp narrative and demo layer for the governed cognitive loop, using the universal human experience of how a careful expert makes a hard decision as the accessible surface and the real three-organ loop as the depth. One story, several formats, all descending through the same layers, all driven and drawn from the live system.

The belief the room walks out repeating: **it makes hard calls the way a careful expert does, and it never skips the step where it tries to prove itself wrong.**

Honesty constraint that overrides everything: the story must not claim optimality or perfection. The guarantee is hard-constraint satisfaction and falsification-gated commit, not that it is always right. Any generated text that implies the loop is optimal or infallible fails the build.

---

## The six governing design laws (same philosophy as the on-ramp discipline, adapted to this loop)

1. **One spine, many formats.** `docs/story-arc.md` is the single source of truth. Demo, walkthrough, lab, and any deck derive from it and stay consistent.
2. **Altitude, not audience.** One descent. No separate shallow and deep artifacts. Every format goes from the expert analogy down to the real organs.
3. **Human surface, better-than-human payload.** Each layer opens on how a good expert works and lands the turn: the loop does the disciplined thing every cycle, where a tired or overconfident human skips it. Never leave the loop looking merely as fallible as a person, and never overclaim it as more than disciplined.
4. **Grounded in the real system, and drawn.** Every beat maps to a real `LoopCycle` behavior, and the invisible parts (horizon, constraints, falsification) are rendered from real cycle data, not illustrated abstractly.
5. **One idea per layer, pulled not pushed.** Each layer introduces one organ, motivated by the thread the previous layer planted.
6. **Complete at every altitude.** Stopping after any layer still delivers a whole story. The falsification hook alone is a complete small demo, which is exactly why it is the extractable partner beat.

---

## Before you write anything

1. Read the `governed-cognitive-loop` repo in full: the `ConstraintClassifier`, `HorizonPredictor`, `ObjectiveInterpreter`, `Controller`, `FalsificationGate`, `LoopDriver`, and the `LoopCycle` ledger chain. Note the honesty boundary in the code: the LLM interprets the objective and predicts disturbances and never computes the committed action or performs constraint satisfaction. The story must show this boundary, not blur it.
2. For every beat below, identify the real cycle state and the real fields that produce it, and write `docs/MAPPING.md`. In particular, identify exactly which cycle data feeds the horizon plot (measured history, predicted trajectory, constraint bounds, committed step, and any rejected action), because that plot is the demo.
3. Confirm the loop can run a deterministic, seedable scenario with a scheduled disturbance and reset cleanly, so an SA can run it live and re-run it. Add a thin seed-and-reset path here if the service lacks one.

---

## The layer map (the arc; refine against the real system, keep the shape)

Each layer has a human truth, the live behavior it maps to, what must be drawn, the thread it plants, the question it provokes, the humor beat, and the turn.

### Layer 0. The hook. The expert tries to prove their own plan wrong before acting.
- **Human truth:** the difference between a novice and an expert is not speed. The novice acts on the first plausible plan. The expert pauses and asks what would make this the wrong call, and the pause is the thing you trust.
- **Live behavior:** the loop proposes an action and the `FalsificationGate` engages before commit, runs disconfirmation checks against evidence, and rejects or passes it. Show a real rejection: the plan assumed something the evidence contradicts, so it does not act.
- **Must be drawn:** the proposed action, the check that failed, and the action being held rather than executed.
- **Thread planted:** it tried to disprove its own plan, against something.
- **Question provoked:** what is it checking the plan against.
- **Humor beat:** it is the colleague who reads the email back before hitting send and catches the mistake, unlike the one who fires first and apologizes later.
- **Turn:** a human does this on a good day. This one does it every cycle and never talks itself out of the check because it is late or sure of itself.

### Layer 1. The evidence. The expert reads the situation, not a stale rulebook.
- **Human truth:** a good expert derives the real constraints from what is in front of them. The junior applies the manual. The expert sees that today is different.
- **Live behavior:** the `ConstraintClassifier` derives constraints from evidence, each with its justification, deterministic first and LLM only for the ambiguous. Show a constraint appear because evidence justified it, and a constraint with no evidence get dropped.
- **Must be drawn:** each active constraint with the evidence attached, and the boundary it imposes shown on the horizon plot.
- **Thread planted:** constraints came from evidence, so they move as the situation moves.
- **Question provoked:** how does it plan under those constraints, and how far ahead does it look.
- **Humor beat:** unlike the manual that still says to do the thing that stopped working two years ago, it notices when the situation changed.
- **Turn:** a human's rules are often habit and stale policy. These constraints carry the evidence that justifies them, so you can check why each one exists.

### Layer 2. The lookahead. Think ahead, commit one step, re-check.
- **Human truth:** a careful expert thinks several moves ahead but does not lock in the whole plan, because the situation will change. They take the next step and reassess. The overcommitter executes a five-step plan even as the facts move.
- **Live behavior:** the `HorizonPredictor` and `Controller` produce a plan over the horizon under the hard constraints, and commit only the first step, then re-plan next cycle on fresh measurements. A scheduled disturbance arrives mid-horizon and the plan is redrawn.
- **Must be drawn:** the horizon plot as the centerpiece, measured history left of a now line, predicted trajectory right of it, constraint boundaries shaded, the committed first step marked, and the trajectory visibly redrawn when the disturbance lands.
- **Thread planted:** it committed only one step and re-planned, and the goal it optimized came from somewhere.
- **Question provoked:** who sets the goal it is optimizing, and can I trust that part.
- **Humor beat:** unlike the person who booked the whole itinerary and refused to change it after the flight was cancelled, it re-plans when reality moves.
- **Turn:** a human overcommits to sunk-cost plans. This one commits only the next step and re-checks every cycle, so it cannot ride a dead plan into a wall.

### Layer 3. The floor. The creative part never touches the safety-critical lever.
- **Human truth:** you want judgment about the goal to be explainable, and you do not want the fast, fallible part of the mind holding the lever that cannot be pulled back. Frame the problem with intuition, execute it with discipline.
- **Live behavior:** the `ObjectiveInterpreter` (the LLM) reads context and re-specifies the objective and predicts disturbances, but the deterministic `Controller` owns constraint satisfaction and the commit. Show the boundary: context changes, the LLM changes the objective, and the controller, not the LLM, computes and guarantees the action. Show the full `LoopCycle` in the ledger: constraints, objective, plan, falsification result, commit, outcome.
- **Must be drawn:** the boundary itself, the LLM feeding the objective in, the deterministic controller producing the guaranteed action, and the ledger chain for the cycle.
- **Thread planted:** the creative part never touches the safety-critical lever, and the whole decision is on the record.
- **Question provoked:** so can I let it run on real decisions.
- **Humor beat:** it lets the imaginative part brainstorm the goal but keeps it nowhere near the launch button, which is more discipline than most org charts manage.
- **Turn:** a human's intuition and their execution live in the same fallible head, and this system claims no optimality either, only that hard constraints hold and the plan survived a challenge. It separates the creative framing from the guaranteed execution and keeps the receipt, which a person cannot.

### The close. The turn, stated whole.
It makes hard calls the way a careful expert does: reads the real constraints from evidence, thinks ahead but commits only the next step, and tries to prove its own plan wrong before acting. Except it never skips the self-challenge, never rides a dead plan, never lets the creative part touch the safety-critical lever, and keeps the receipt every time. It does not promise to be right. It promises to stay inside the limits and to have tried to prove itself wrong first. That is the sentence they repeat.

---

## Deliverables (all derived from the one spine, all consistent with the layer map)

1. **`docs/story-arc.md`** the canonical spine and layer map. Source of truth.
2. **The demo driver with the horizon visualization as its hero.** A navigable runner that drives the live loop and draws it. Requirements: it runs real cycles and renders the horizon plot (history, now line, predicted trajectory, constraint boundaries, committed step, rejected action) from real cycle data; each layer is an independently runnable scene; the SA can jump to any layer in any order and stop after any layer; it seeds a deterministic scenario with a scheduled disturbance and resets cleanly. If the horizon does not render clearly from real data, the demo does not exist, so this is the first thing to get right.
3. **`docs/walkthrough.md`** the SA's navigation map, not a linear script. Per layer: what is on screen and drawn, the thread, the provoked question, the humor beat, the turn, how to descend, how to stop cleanly, and the hard technical question each layer invites with the answer that opens the next. Include a controls-literate FAQ (why not just reactive, where is optimality, why is the LLM allowed near this at all), because this room will ask.
4. **The lab** hands-on modules (Antora or Showroom style for RHDP, else markdown) where a learner runs the real loop and watches a rejected plan, a redrawn horizon, and a full ledger cycle. One module per layer, each completable on its own.
5. **(optional) technical deck** the layers as slides sharing the identical spine, built so the presenter descends by opening the live demo, not by switching stories.

For `partner_extracted_beat`: build only `docs/story-arc.md` scoped to Layer 0 and the close, plus the demo driver scene for the falsification hook pointed at a felt-stakes domain, plus a short walkthrough. Drop the horizon and constraint depth. The beat is "it tries to prove its own plan wrong before acting," and it is complete on its own.

---

## Humor guidance

Load-bearing, dry, professional. Each funny beat lands on a concept transition and works as a comprehension checkpoint, because the joke only lands if the room already mapped the human situation onto the loop. Use the beats above. Every humor beat sits beside its turn, and none may leave the loop looking as fallible as a person or as more than disciplined.

---

## EDD rubric grid for the content (green is required to pass)

| Dimension | Red | Yellow | Green |
|-----------|-----|--------|-------|
| One spine | Formats diverge | Minor drift | All formats match the canonical layer map |
| Altitude not audience | Separate shallow and deep artifacts | One track with a shallow variant | One descent, every format goes expert-surface to real-organ depth |
| Grounded and drawn | Beat mocked or only narrated | Real but not rendered | Every beat maps to real cycle data, and the invisible parts are drawn from it |
| Horizon is the hero | No plot, or a fake plot | Plot from synthetic data | Horizon rendered from real cycle data, redraws live on the disturbance |
| The turn present | Analogy with no turn | Turn only at the close | Every layer lands its better-than-human turn |
| No overclaim | Text implies optimal or infallible | Ambiguous language | States the guarantee is constraint satisfaction and self-challenge, not perfection |
| LLM boundary shown | Story lets the LLM own the action | Boundary implied | Story shows the LLM setting only the objective, the controller guaranteeing the action |
| One idea per layer | Multiple organs per layer | Two blurred | Exactly one organ per layer, pulled by the prior thread |
| Complete at every altitude | Only pays off at the bottom | Weak early stops | Any layer stops cleanly, and Layer 0 stands alone as the partner beat |
| Navigable instrument | Linear only | Partly jumpable | Any layer runnable in any order, live, clean reset |
| No em-dashes | Present | A few slip | None anywhere |

---

## preflight.sh

Checks: the governed-cognitive-loop service is reachable and healthy, a deterministic scenario with a scheduled disturbance can be seeded and reset, real cycle data exposes the fields the horizon plot needs, MAPPING.md exists and references only real cycle behavior, and the LLM-boundary field is inspectable so the story can show it. Exits non-zero with a clear message on any failure.

## verify.sh

Runs, in order: preflight, a run of the demo driver executing each layer independently against the live loop and asserting the real beat occurred (a real falsification rejection, real evidence-justified constraints, a real one-step commit with a horizon redraw on the disturbance, a real full ledger cycle, and the LLM never producing the committed action), a render check that the horizon plot is built from real cycle data and redraws on the disturbance, a consistency check that deck, walkthrough, and lab reference the same canonical layer map, an overclaim check that no generated text asserts optimality or infallibility, and an em-dash check. Prints a one-line pass summary and exits 0 only if every check passes.

## Definition of Done

verify.sh exits 0. One canonical spine, every format descends through it. Every beat is produced by the real loop and the horizon is drawn from real cycle data and redraws live. The LLM-boundary is shown, not blurred. No optimality or infallibility is claimed anywhere. Every layer lands its turn and is complete on its own, and Layer 0 stands alone as the extractable partner beat. The room walks out repeating the belief sentence. No em-dashes anywhere.
