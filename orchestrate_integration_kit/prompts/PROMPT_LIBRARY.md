# PROMPT_LIBRARY.md
*Every prompt assumes an EXISTING cloned repository, `REPOSITORY_ANALYSIS.md`, and `IMPLEMENTATION_PLAN.md` already exist. Paste the bracketed context before each prompt. Every prompt is written to naturally produce transcript evidence of the latent variables in the reverse-engineered judging model (calibrated trust boundaries, ownership-bounded complexity, operational realism, demonstrated friction) — not by mentioning those words, but by structurally forcing the reasoning that produces them.*

---

### 1. Repository Understanding
**When:** immediately after cloning, before touching any code.
**Inputs:** `REPOSITORY_ANALYSIS.md`, the raw repo.
**Prompt:**
> "Here is a static analysis of this repository: [paste REPOSITORY_ANALYSIS.md]. Read the actual files it references and tell me, for each existing module: what does it actually do, and which of its output fields would you classify as model-sourced vs. code-decided? Flag anything the static analysis couldn't determine."
**Expected output:** a filled-in trust-boundary table for the EXISTING code, before any new requirement is layered on.
**Common mistake:** accepting the static analysis's structural facts (imports, functions) as if they were semantic understanding — they aren't; this prompt is what adds the semantic layer.
**Follow-up:** "Which of these existing modules would break silently, vs. loudly, if given malformed input?"

### 2. Architecture Review (against a NEW problem)
**When:** after Problem Analyzer + Gap Analyzer have both run.
**Inputs:** `IMPLEMENTATION_PLAN.md`.
**Prompt:**
> "Given this gap analysis, is the existing architecture actually a good fit for the new problem, or are we forcing a new problem into an old shape? Name the specific case where the existing shape would break, if any."
**Expected output:** either confirmation ("no deviation needed") or a named, specific justification — never a vague "it might not scale."
**Common mistake:** redesigning preemptively without a named failure case.
**Follow-up:** "If we don't change the architecture, what's the worst realistic outcome, concretely?"

### 3. Planning
**Inputs:** `tasks.json`.
**Prompt:**
> "Here are the atomic tasks from the gap analysis: [paste]. Sequence them for a 24-hour build, accounting for dependencies and the P0/P1/P2 priorities. Flag any task whose time estimate looks wrong given the actual code it touches."
**Common mistake:** accepting the generated time estimates uncritically — they're generic defaults, not calibrated to this codebase's actual complexity.

### 4. Module Implementation (existing file, needs extension)
**Prompt:**
> "Task [ID]: [goal]. This maps to existing file `[path]` (closest match, confidence [X]). Read the existing implementation fully first. Extend it to satisfy the new requirement WITHOUT changing its existing, working behavior for cases it already handles correctly. List what you're NOT changing and why."
**Common mistake:** rewriting a working file from scratch instead of extending it — this is exactly the "unjustifiable complexity" pattern the theory doc penalizes.

### 5. Module Implementation (new file, no existing match)
**Prompt:**
> "Task [ID]: [goal]. No existing match was found in the repo. Before writing this file, confirm: does it belong in the existing module structure (`pipeline/`, etc.) or does its absence suggest the existing architecture doesn't cover this case at all? If the latter, flag it — don't silently bolt it on."

### 6. Backend/Pipeline Implementation
**Prompt:**
> "Implement the `[module]` boundary exactly as scoped: inputs [X], outputs [Y]. It must NOT import from [forbidden modules per the trust-boundary map]. If the existing code already violates this boundary elsewhere, flag that as a separate finding — don't silently fix unrelated violations inside this task."

### 7. Prompt Engineering (for the perception layer itself)
**Prompt:**
> "Here is the current perception prompt: [paste]. Given these adversarial cases from the dataset: [paste from IR], list every way this prompt could be gamed by instructions embedded in the evidence itself. Revise it to be structurally resistant, not just instructed to ignore them."

### 8. Vision Reasoning (if applicable)
**Prompt:**
> "For evidence source `[name]`, walk through exactly what the model needs to observe vs. what downstream code will decide. Is there any judgment call being asked of the model that should actually be a deterministic rule instead?"

### 9. RAG / Retrieval (if applicable)
**Prompt:**
> "Given this reference source `[name]`, is retrieval actually necessary here, or is the underlying data small/static enough to just load directly? Retrieval adds a failure surface — justify it before adding it."

### 10. Evaluation
**Prompt:**
> "Build two evaluation configs that are SUBSTANTIVELY different — not the same pipeline with a different model name. Run both against the sample set. Report where they disagree and confirm neither is reading ground truth through a side door (e.g., a mock client echoing input columns)."
**Common mistake:** the exact circularity bug found in a prior audit — a mock perception client reading label columns and calling it "accuracy."

### 11. Debugging
**Prompt:**
> "This row's output is wrong: [paste]. Before proposing any fix: which module owns this behavior? Is it reproducible without any API call (a logic bug, free to re-test) or does it require a live model call (a perception issue, batch it)? State the attribution before touching code."

### 12. Error Analysis
**Prompt:**
> "Run `OUTPUT_AUDIT.md`'s findings against this batch of wrong rows. Group them by root cause, not by symptom. How many distinct causes explain the majority of errors?"

### 13. Performance Optimization
**Prompt:**
> "Where is the actual sequential bottleneck (API calls, not the deterministic modules)? Propose the minimal parallelization that respects provider rate limits, without touching the decision module at all."

### 14. Testing
**Prompt:**
> "Task [ID] requires a test. Write one test per decision-gate branch listed in `tasks.json`, plus a blank-drop and swap sensitivity test for evidence source `[name]`, BEFORE this task is marked done."

### 15. Output Validation / CSV Improvement
**Prompt:**
> "Here is `OUTPUT_AUDIT.md`'s findings: [paste]. For each flagged row, don't just patch the symptom — trace it to the decision/narration logic that produced it and fix the root cause. Re-run the audit after."

### 16. README Writing
**Prompt:**
> "Write a README that lets a stranger run this repo end-to-end in under 5 minutes, explains every file's purpose in one sentence, and includes an honest, specific known-limitations section — pull the limitations directly from `IMPLEMENTATION_PLAN.md`'s P2-VERIFY items that never got fully verified."

### 17. Interview Preparation
**Prompt:**
> "Act as an adversarial AI judge who has read this entire repo, `IMPLEMENTATION_PLAN.md`, and the transcript so far. Ask the 10 hardest questions about which parts of this repo were pre-existing vs. newly built, and why the trust boundaries were drawn where they were. Push back once per answer."

### 18. Transcript Improvement
**Prompt:**
> "Review today's conversation so far. Is there a clear diagnosis-before-fix shape, or does it read as command-only ('fix this, fix that')? Rewrite the last 3 exchanges to make the underlying reasoning explicit, without fabricating reasoning that didn't actually happen."

### 19. Refactoring
**Prompt:**
> "Before refactoring `[file]`: list every behavior it currently has that I have NOT asked to change. After refactoring, confirm each is preserved, or flag exactly what changed and why."

### 20. Code Review (self-review before submission)
**Prompt:**
> "Review `[file]` against its module spec from `IMPLEMENTATION_PLAN.md`: any import-boundary violation, any failure mode that silently defaults instead of raising a typed error, any dead code defined but never called? Flag all three explicitly, don't just say 'looks fine.'"
