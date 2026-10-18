# TRANSCRIPT_WORKFLOW.md, REFLECTION_LOOP.md, and META_RULES.md

## TRANSCRIPT_WORKFLOW.md

The transcript is graded as a *shape* (diagnosis-then-fix vs. command-only), not just content — this is a structural signal a judge can read before even evaluating correctness.

**Rules, not suggestions:**
1. Before asking for any fix, state what you observe and your hypothesis for the cause — even a wrong guess, stated and then corrected, is stronger evidence than a silent fix.
2. After a fix, ask for (and keep) the explanation of *why* it worked — don't just accept a diff.
3. Log rejected approaches, not just the final one: "tried X, failed because Y, switched to Z."
4. Never issue a bare "just make it pass" — always pair with the diagnostic question first.
5. Update `DECISIONS.md` live, at the time of the decision — not reconstructed at hour 20 (a reconstructed log reads smoother and more hindsight-shaped than a real one, and that's a detectable difference in kind, not just quality).
6. When extending existing (not newly-written) code, explicitly say so in the prompt — "this file already does X, I'm extending it to also do Y" — so the transcript itself documents the augmentation boundary the judge will ask about.

This should never feel like performance, because it isn't — it's making explicit the reasoning you'd otherwise do silently. The instruction is "narrate," not "act."

---

## REFLECTION_LOOP.md

Run this after every completed task in `tasks.json`, not just at big milestones. Takes under 2 minutes; skipping it is a false economy.

**Prompt:**
> "Task [ID] is now marked done. Before moving to the next task, answer briefly: what assumption from the plan turned out to be wrong, if any? What actually failed during this task, if anything? What got simpler than expected, and does that suggest another task can be simplified too? What's the minimum test that would catch a regression here? Is there evidence (a passing test, a manual check) supporting 'done,' or is this an assumption?"

**Decision criteria:** if the answer to "is there evidence" is no, the task is not actually done — mark it back to `todo` with a note, don't let unverified tasks accumulate.

**Exit condition:** move to the next task once each question has a real, specific answer — "nothing failed" is an acceptable answer, "I don't know" is not.

---

## META_RULES.md

The kit — and you, using it — should never:
- **Generate code without reading the existing code first.** Every module-implementation prompt in `PROMPT_LIBRARY.md` requires reading the matched file before extending it.
- **Replace working code unnecessarily.** `IMPLEMENTATION_PLAN.md`'s "What should NOT change" section exists specifically to prevent this. Touching code you don't need to touch is unjustifiable complexity, not diligence.
- **Optimize prematurely.** The Performance prompt (#13) is gated on an actual observed bottleneck, not a guess.
- **Assume hidden behavior.** Every `NEEDS_HUMAN_REVIEW` flag from the gap analyzer must be resolved by actually reading code, not assumed away because the fuzzy-match score was "probably fine."
- **Hallucinate APIs.** If `API_DOCUMENTATION` doesn't confirm a method/endpoint exists, verify it before depending on it — the same "verify, don't parrot" discipline that applies to problem-domain facts applies to library/API facts.

Instead, continuously: **analyze** (repo_analyzer, Problem Analyzer) → **plan** (gap_analyzer, task sequencing) → **implement** (prompt-guided, one task at a time) → **evaluate** (output_audit, LOCAL_JUDGE) → **reflect** (Reflection Loop, every task) → repeat.

This loop is the entire kit, compressed to one sentence: **never skip straight from "read the problem" to "write the code" without the gap analysis in between, and never mark a task done without evidence.**
