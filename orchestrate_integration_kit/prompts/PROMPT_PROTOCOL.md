# PROMPT_PROTOCOL.md
*16 templates. Each one is short by design — length doesn't produce a better transcript, structure does. Every template forces the same underlying shape: read → hypothesize → plan → act → verify → reflect, because that shape is what the reverse-engineered judging model rewards (ownership, calibrated trust boundaries, demonstrated friction), not the words used to ask for it.*

---

### 1. Repository Review
**Objective:** build a real mental model of existing code before touching anything.
**Template:**
> "Read `[path/module]`. Summarize: what it does, what calls it, what it assumes about its inputs. Don't propose changes yet."
**Why it produces a better log:** separates *understanding* from *acting* as two distinct, visible turns — a judge sees you read before you wrote, which is the single cheapest ownership signal available.
**Common mistakes:** skipping this and going straight to a fix; asking the agent to "explain the whole repo" in one shot (too broad to be checkable later).
**Example usage:** first prompt after cloning, one call per unfamiliar module.

---

### 2. Architecture Review
**Objective:** confirm or challenge the existing shape before adding to it.
**Template:**
> "Given [new requirement], does the current architecture in `[module]` fit, or would it break somewhere specific? Name the exact case, don't speak in generalities."
**Why it produces a better log:** forces a *named* failure case instead of vague "this might not scale" — this is the exact tell the interview later probes for, so getting it in writing now means you can just read it back.
**Common mistakes:** accepting "seems fine" as an answer; redesigning preemptively without a concrete case.
**Example usage:** before starting any task that touches more than one existing module.

---

### 3. Problem Analysis
**Objective:** turn a raw problem statement into a concrete success criterion.
**Template:**
> "In one sentence: what does a CORRECT output row mean for this problem? List every field's trust boundary — is it something a model can be uncertain about, or must it be a deterministic rule?"
**Why it produces a better log:** this is the trust-boundary map, made explicit and timestamped early — later prompts can just reference it instead of re-deriving it.
**Common mistakes:** treating this as optional busywork; doing it after implementation has already started.
**Example usage:** hour 0, once, before any code.

---

### 4. Feature Design
**Objective:** decide the shape of a new capability before writing it.
**Template:**
> "I need [feature]. Propose the minimal design that satisfies it. What's the simplest version that could work, and what's the one case that would force something more complex?"
**Why it produces a better log:** biases toward restraint on the record — "I considered X, rejected it because Y" is stronger transcript material than a feature appearing fully-formed.
**Common mistakes:** skipping straight to "implement X"; accepting the first design without asking what it trades away.
**Example usage:** any time a new module or capability is being added, not extended.

---

### 5. Implementation
**Objective:** write code against an already-agreed plan, not as the first act of thinking.
**Template:**
> "Implement [specific, already-agreed piece]. Don't change anything outside its stated scope. List what you're deliberately not touching."
**Why it produces a better log:** explicit scope + explicit non-changes is exactly the "ownership-bounded complexity" signal — every line added is traceably justified.
**Common mistakes:** using this as the FIRST prompt for a new feature (skips design, see #4); letting scope silently creep.
**Example usage:** only after #2, #3, or #4 have already produced a plan.

---

### 6. Refactoring
**Objective:** change structure without changing behavior, provably.
**Template:**
> "Before refactoring `[file]`: list its current behaviors. After refactoring: confirm each is preserved, or flag exactly what changed and why."
**Why it produces a better log:** the before/after list is a cheap, self-generated regression check that reads as rigor, not just "cleaned up the code."
**Common mistakes:** refactoring and testing simultaneously (conflates two different kinds of change, makes attribution impossible if something breaks).
**Example usage:** only on code that already has some test coverage or a clear behavior list — never as a first touch on unfamiliar code.

---

### 7. Debugging
**Objective:** attribute a failure to a specific cause before fixing it.
**Template:**
> "This is wrong: [paste]. Before proposing a fix: is this reproducible without any API call (logic bug) or does it need a live model call (perception issue)? State which, and why, first."
**Why it produces a better log:** attribution-before-fix is the single most repeated pattern across every winner account in this corpus — it's cheap to do and expensive to fake convincingly if you didn't actually do it.
**Common mistakes:** "just make it pass"; re-running the same fix hoping for a different result without ever stating a hypothesis.
**Example usage:** every time output is wrong, before any code changes.

---

### 8. Hypothesis-Driven Investigation
**Objective:** for non-obvious bugs, force a falsifiable guess before poking around.
**Template:**
> "What's your hypothesis for why this happens? What's the minimal check that would confirm or kill that hypothesis?"
**Why it produces a better log:** produces the exact "I thought X, tested it, was wrong, then found Y" shape that's the hardest pattern to fake and the strongest interview material available.
**Common mistakes:** skipping to a fix once a hypothesis "feels" right without the confirming check.
**Example usage:** after #7 attributes the failure to a logic bug but the cause still isn't obvious.

---

### 9. Testing
**Objective:** get real coverage on the parts that are expensive to be wrong about.
**Template:**
> "Write one test per branch in `[decision function]`, before any live run. Include a pass case and a fail case for each."
**Why it produces a better log:** cheap, checkable, and directly demonstrates the "tested the parts where being wrong is expensive" prioritization the theory identifies as rewarded — not exhaustive fuzzing, targeted coverage.
**Common mistakes:** writing tests after the live run instead of before; testing trivial code while leaving the decision logic untested.
**Example usage:** immediately after any decision-gate implementation, before it's ever run against real data.

---

### 10. Hidden-Test / Adversarial Robustness
**Objective:** find and close the gaps a hidden test set would exploit.
**Template:**
> "Given these adversarial patterns in the sample data: [list]. For each, confirm the pipeline handles it structurally, not just 'probably fine.' Then propose one more adversarial case NOT in this list that the current data might be hinting at."
**Why it produces a better log:** the "propose one more" clause is what separates genuine robustness thinking from checklist-following — it's a small ask with outsized signal value.
**Common mistakes:** treating this as a one-time pass instead of revisiting it after each new feature; only checking patterns already in the sample data.
**Example usage:** once after initial build, again right before submission.

---

### 11. Evaluation
**Objective:** get a real, non-circular accuracy signal.
**Template:**
> "Build two SUBSTANTIVELY different eval configs — not the same pipeline with a different model name. Run both. Report disagreements. Confirm neither reads ground truth through a side door."
**Why it produces a better log:** explicitly naming the circularity risk on the record means you can't accidentally walk into it and not notice.
**Common mistakes:** one config only; a mock perception client that echoes label columns back as "accuracy."
**Example usage:** once a full pipeline run is possible, before the final submission run.

---

### 12. Performance
**Objective:** fix a real, measured bottleneck — not a guessed one.
**Template:**
> "Where is the actual sequential bottleneck, measured, not assumed? Propose the minimal parallelization within provider rate limits, without touching decision logic."
**Why it produces a better log:** "measured, not assumed" on the record prevents a wasted-hour optimization detour and reads as judgment, not busywork.
**Common mistakes:** optimizing before measuring; touching deterministic logic while "just" trying to speed up perception calls.
**Example usage:** only if wall-clock time genuinely threatens the 24-hour deadline.

---

### 13. Operational Resilience
**Objective:** confirm the system survives its environment's real failure modes.
**Template:**
> "Simulate killing this mid-run (rate limit / network drop). Does it resume correctly, or lose progress? If it loses progress, that's the next task, not a footnote."
**Why it produces a better log:** proactive, not reactive — matches the "operational realism" pattern shown to differentiate elite from mid-pack builds.
**Common mistakes:** only discovering this the hard way, mid-competition, under real time pressure.
**Example usage:** once basic perception integration exists, before the full sample-set run.

---

### 14. Output/CSV Validation
**Objective:** catch schema, consistency, and templating problems before submission.
**Template:**
> "Check output.csv: header exact match, enum conformance per field, duplicate rows, and justification-text diversity (are reasons genuinely per-row or templated?). Report each separately."
**Why it produces a better log:** explicitly asking about templated justifications targets a real, previously-observed failure class (3 fixed reason strings across 44 rows) rather than a generic "check for errors."
**Common mistakes:** eyeballing a few rows instead of checking the full set; not checking justification diversity specifically.
**Example usage:** after every full pipeline run, not just once at the end.

---

### 15. Submission Audit
**Objective:** verify the thing you're about to submit actually works, cold.
**Template:**
> "Extract this exact zip/repo to a clean directory and run the entrypoint end to end. Report the literal output, not a summary of what should happen."
**Why it produces a better log:** "literal output, not a summary" prevents the agent (or you) from asserting success without having actually seen it.
**Common mistakes:** trusting that it "should still work" because nothing was changed since the last successful run; skipping this under time pressure — this is exactly when it matters most.
**Example usage:** last 60–90 minutes, and again immediately before the final submit action.

---

### 16. Interview Preparation
**Objective:** convert the actual build into defensible, specific answers.
**Template:**
> "Act as an adversarial judge who has read this repo and this transcript. Ask the 10 hardest questions about tradeoffs I made and rejected. Push back once per answer."
**Why it produces a better log:** the pushback clause specifically targets overclaiming before a real judge does — cheap rehearsal for the highest-variance, hardest-to-fake scoring stage.
**Common mistakes:** doing this only once; doing it too early, before the repo's final state is stable, so the questions go stale.
**Example usage:** once mid-build (rough pass), once final (real pass, last 90 minutes).
