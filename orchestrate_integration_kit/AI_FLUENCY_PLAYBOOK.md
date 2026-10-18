# AI_FLUENCY_PLAYBOOK.md
*Reverse-engineered from winner accounts + prior forensic audits. Six characteristics, each with what it looks like in a real prompt vs. what it isn't. Verbosity is not on this list on purpose — none of these require more words, just a different shape.*

---

### 1. Ownership
**What it is:** the prompt shows YOU already have a model of the system, and you're directing the agent within it — not handing over a blank check.
**Looks like:** "This file already validates X; extend it to also check Y without changing its existing behavior."
**Isn't:** "Add Y to the validation" (no evidence you know what's already there).
**Log effect:** a reader can tell, from the prompt alone, that a person understood the system before asking for a change — this is legible without even reading the response.

### 2. Engineering Judgment
**What it is:** the prompt asks for a decision with stated criteria, not just an output.
**Looks like:** "What's the simplest version that could work, and what case would force something more complex?"
**Isn't:** "Design the best architecture for this."
**Log effect:** "best" has no falsifiable answer and produces generic output; a named tradeoff criterion produces a response you can actually evaluate and defend later.

### 3. Hypothesis-Driven Debugging
**What it is:** a guess is stated and checked, not just a fix applied.
**Looks like:** "Is this reproducible without an API call, or does it need a live call? Which, and why?"
**Isn't:** "Fix this bug."
**Log effect:** this is the single hardest pattern to fake after the fact — a transcript either shows a real hypothesis-then-check cycle or it doesn't, and a judge reading it live can tell the difference in seconds.

### 4. Validation
**What it is:** every change ends with an explicit, checkable claim, not an assumption of success.
**Looks like:** "Confirm this by running X — report the literal output."
**Isn't:** "This should work now."
**Log effect:** distinguishes "I verified this" from "I hope this," which is exactly the axis the interview stage probes hardest — practicing it in the transcript is free rehearsal.

### 5. Architecture Awareness
**What it is:** the prompt references the existing shape of the system, not just the local change.
**Looks like:** "Does this fit the existing decision/perception split, or does it need to cross that boundary?"
**Isn't:** implementing a feature with no reference to where it sits in the whole.
**Log effect:** shows the system is held as a whole in your head, not assembled piecemeal — this is what "ownership-bounded complexity" looks like turn by turn, not just at the end.

### 6. Tradeoff Reasoning
**What it is:** an alternative is named and rejected, not just the chosen path described.
**Looks like:** "I considered a multi-agent split here; rejected it because [specific case]."
**Isn't:** presenting one design as if it were the only option.
**Log effect:** the strongest, most repeated pattern across every winner account — a rejected alternative with a named reason is more convincing than any amount of confidence in the chosen one.

---

## The anti-pattern to avoid: artificial verbosity
None of the six characteristics above require longer prompts. A short prompt that names a hypothesis beats a long prompt that doesn't have one. If you find yourself padding a prompt with explanation to "sound more thorough," stop — the judging signal comes from the *shape* of the exchange (read → hypothesize → plan → act → verify → reflect), not its word count. A 15-word prompt that states a falsifiable hypothesis outscores a 150-word prompt that doesn't.

## The single fastest self-check
Before sending a prompt, ask: **"If I only had this prompt and the agent's reply, with no other context, would it be obvious I understood the system before asking for a change?"** If no, it's missing one of the six characteristics above — usually #1 or #6.
