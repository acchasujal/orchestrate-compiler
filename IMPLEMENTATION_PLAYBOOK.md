# IMPLEMENTATION_PLAYBOOK.md — Message Notification Router
*Architecture is frozen (ARCHITECTURE_DESIGN.md). This document is execution only. No redesign below — if a critical flaw surfaces during implementation, stop and flag it explicitly rather than silently deviating.*

---

## PHASE 1 — CRITICAL PATH ANALYSIS

```
context_resolver ──┬── retrieval ─────────────────────┐
  (P0, no deps)     ├── risk_scorer ────────────────────┤
                     ├── personalization ───────────────┼── decision_engine ── justification ── orchestrator ── evaluation
                     └── perception ── content_judgment ─┘
                         (only 23 rows)  (gated, ~10-15 rows)
```

**On the critical path (block everything downstream):** `context_resolver` → `decision_engine` → `justification` → `orchestrator`. If any of these slip, the whole timeline slips.

**Independently developable, in parallel, once `context_resolver` exists:** `retrieval`, `risk_scorer`, `personalization`, `perception`. None of these depend on each other; all four can be built by different mental "tracks" in the same session without blocking.

**Should never block others:** `perception` and `content_judgment` — both touch a live model provider and are the only real latency/cost/flakiness risk in the system. Everything else must be fully buildable and testable with zero network calls, specifically so a provider outage or rate limit never stalls the other 80% of the work.

**Never on the critical path, build last, cut first if time runs short:** `evaluation` harness polish beyond the minimum needed for Phase 5 checkpoints, and any LLM-upgrade to `justification` (templates are the P0 deliverable; LLM-written prose is a P2 stretch goal per ARCHITECTURE_DESIGN.md Phase 2).

---

## PHASE 2 — IMPLEMENTATION STRATEGY, PER MODULE

### `context_resolver`
- **Purpose:** join `messages.csv` row against 6 context CSVs into one typed object.
- **Interfaces:** `resolve(message_row) -> ResolvedContext`. **Inputs:** raw row + loaded DataFrames. **Outputs:** `ResolvedContext` (typed).
- **Acceptance:** all 110 rows resolve with zero `KeyError`/`None`-crash, including nullable FKs (`group_id`, `business_id`, `sender_user_id` all confirmed nullable in research).
- **Tests:** one fixture per nullable-FK combination (personal/group/business row shapes).
- **Mock strategy:** none needed — this is pure pandas joins, no external dependency to mock.
- **Failure modes:** a `user_id` not in `users.csv` (research confirmed 100% integrity, so this should never happen — if it does, treat as a data anomaly and log loudly, don't silently default).
- **Complexity:** low. **Risk:** low. **Time:** ~1h.

### `retrieval`
- **Purpose:** deterministic candidate evidence selection from `message_history.csv`/`message_events.csv`.
- **Interfaces:** `get_candidates(user_id, sender_id, business_id, topic_hint) -> EvidenceCandidates`.
- **Acceptance:** every returned ID verified to exist in `message_history.csv` AND belongs to the queried `user_id`.
- **Tests:** `msg_021`/`msg_022`-style near-duplicate case — confirm candidates differ appropriately when the risk-bearing clause differs.
- **Mock strategy:** none needed — pure pandas filtering.
- **Failure modes:** empty candidate set → must return empty list, downstream must accept this and emit `none`, not force a citation.
- **Complexity:** low-medium. **Risk:** low. **Time:** ~2h.

### `risk_scorer`
- **Purpose:** hybrid — deterministic hard-triggers (domain mismatch, injection pattern) + model soft score.
- **Interfaces:** `score_risk(context, observation) -> RiskSignal(hard_override, soft_risk_score, matched_rule_name)`.
- **Acceptance:** correctly hard-triggers on all 8 domain-mismatch businesses and `msg_110` — **this is the highest-priority correctness bar in the whole system**, since it's the one unconditional rule the problem statement states explicitly.
- **Tests:** named regression cases for `msg_110` and each of the 8 domain-mismatch businesses (Chase, Green Cross, Thrillophilia, HDFC, Talabat, Polaris, Amazon, RazorpayX).
- **Mock strategy:** the deterministic half needs no mock; the soft-score model call should be developed against a stub returning a fixed score first, real model wired in last.
- **Failure modes:** model call for soft score fails → hard-triggers must still fire independently (they don't depend on the model call succeeding).
- **Complexity:** medium. **Risk:** **highest in the system** — get this module's tests green before anything downstream is trusted. **Time:** ~2h.

### `personalization`
- **Purpose:** deterministic lookup — mute state, opt-out, quiet hours, engagement band.
- **Interfaces:** `score_personalization(context) -> PersonalizationSignal`.
- **Acceptance:** correct for all 110 rows against manually spot-checked expected values on a sample of 10.
- **Tests:** fixture-based, no API needed.
- **Mock strategy:** none needed.
- **Failure modes:** none expected — pure lookup over confirmed-clean data.
- **Complexity:** low. **Risk:** low. **Time:** ~1h.

### `perception`
- **Purpose:** OCR (image) / ASR (voice) → typed `Observation`, only for the 23 media rows.
- **Interfaces:** `perceive(media_type, file_path) -> Observation`.
- **Acceptance:** runs on all 23 media rows; degrades to `Observation(failed=True)` on any provider error, never crashes.
- **Tests:** blank-drop (null the file reference, confirm downstream degrades correctly) and swap (change the file, confirm output changes) — per the Prompt Protocol's universal sensitivity-test pattern.
- **Mock strategy:** **build and test the entire rest of the pipeline against a stub `perceive()` that returns a fixed placeholder Observation first.** Wire in the real provider only once `decision_engine`/`justification` are already passing their own tests — this isolates the one real external dependency to the smallest possible window.
- **Failure modes:** provider timeout/rate-limit/malformed response — all three must degrade to the same safe `failed=True` state, never a raised exception that kills the row.
- **Complexity:** medium (provider integration). **Risk:** medium (only real network dependency). **Time:** ~3h.

### `content_judgment`
- **Purpose:** the one model-owned decision — `genuine_urgency` / `generic_forward` / `ambiguous`, gated to fire only on structural conflict.
- **Interfaces:** `judge_content(context, observation) -> ContentRead`, called only when `decision_engine` detects gate-3 conditions (muted + mentioned).
- **Acceptance:** correctly separates `msg_040` (→ `generic_forward`) from `msg_056` (→ `genuine_urgency`) — **this exact pair is the acceptance test, not a proxy for one.**
- **Tests:** the two named messages, plus 2–3 synthetic near-analogues (same shape, different content) to confirm it's not simply memorizing the two known cases.
- **Mock strategy:** same as `perception` — stub first, wire real model in last, only after `decision_engine`'s gate-3 branch is otherwise fully tested against the stub.
- **Failure modes:** model call fails → falls back to `ambiguous`, which routes conservatively to `digest` per the decision engine's tie-break rule.
- **Complexity:** medium. **Risk:** medium — this is the one place correctness is irreducibly probabilistic; budget real iteration time here, don't expect first-try success. **Time:** ~2h, plus buffer.

### `decision_engine`
- **Purpose:** the gate chain — sole owner of `action`/`message_type`.
- **Interfaces:** `decide(DecisionInput) -> Disposition`. Pure function, no network, no file I/O.
- **Acceptance:** one test per gate branch (5 gates from ARCHITECTURE_DESIGN.md Phase 5), priority order never violated — a gate-1 hard-override must win even if a later gate's inputs would suggest otherwise.
- **Tests:** full branch coverage BEFORE the first live run — this is non-negotiable per the frozen architecture's own principle #6.
- **Mock strategy:** none needed — this is pure logic, testable entirely with hand-built fixtures.
- **Failure modes:** none acceptable — a crash here means a missing output row, which is worse than any wrong-but-present prediction.
- **Complexity:** medium-high (careful priority ordering). **Risk:** high if under-tested, low if the branch-coverage bar is actually met. **Time:** ~3h.

### `justification`
- **Purpose:** `reason`/`confidence`/`evidence_message_ids`, derived only from the locked `Disposition`.
- **Interfaces:** `justify(Disposition, fired_gate, evidence_candidates) -> Justification`.
- **Acceptance:** never contradicts the `Disposition` it describes (checkable by construction, since it has no other input); confidence bands match ARCHITECTURE_DESIGN.md Phase 5's rule (gate-1 → 0.85–0.92, gate-3 → 0.78–0.82, gate-4/5 clean → 0.83–0.89).
- **Tests:** a consistency-audit function — even though templates make contradiction structurally near-impossible, write the check anyway (this is the exact thing a prior submission built and then forgot to call; don't repeat that specific mistake).
- **Mock strategy:** none needed.
- **Failure modes:** none acceptable.
- **Complexity:** low-medium. **Risk:** low. **Time:** ~2h.

### `orchestrator`
- **Purpose:** sequence all modules, one row per input row, checkpointed, fault-isolated.
- **Interfaces:** `run_batch(messages_df) -> output.csv`.
- **Acceptance:** exactly 110 output rows, one per input `message_id`, no duplicates, no missing IDs.
- **Tests:** full 110-row dry run against stubbed `perception`/`content_judgment` first, then again with real providers.
- **Mock strategy:** N/A (consumes the other modules).
- **Failure modes:** any single row's failure must not abort the batch — catch, log, emit a conservative default row (`action=digest`, low confidence, explicit `reason` noting the failure) rather than skip the row entirely.
- **Complexity:** low-medium. **Risk:** low if module contracts are honored. **Time:** ~2h.

**Why this order is optimal:** `context_resolver` first because everything depends on it and it has zero risk. The three pure-lookup modules (`retrieval`, `risk_scorer`'s deterministic half, `personalization`) next, in parallel, because they're independently low-risk and unblock `decision_engine`'s skeleton immediately. `perception` and `content_judgment` are deliberately built against stubs first and real providers last — this means the single highest-risk, highest-latency dependency in the system is introduced only after everything else already works, so a provider problem at hour 10 doesn't threaten the whole day.

---

## PHASE 3 — PARALLELIZATION

**Build simultaneously (no shared dependency once `context_resolver` exists):** `retrieval`, `risk_scorer` (deterministic half), `personalization`.

**Mock/stub first, always:**
- `perception.perceive()` → stub returns a fixed `Observation` regardless of input.
- `content_judgment.judge_content()` → stub returns `ambiguous` regardless of input.
- `risk_scorer`'s soft-score model call → stub returns a fixed mid-range score; the deterministic hard-triggers are real from the start (they need no stubbing, they're pure rules).

**Require real providers, wired in last:** the actual OCR/ASR calls inside `perception`, and the actual model call inside `content_judgment`. Nothing else in the system touches a network call.

**Rule for graduating from stub to real:** only swap a stub for the real provider once every module downstream of it already passes its own tests against the stub's fixed output. This guarantees that when the real provider is wired in, any new failure is attributable specifically to the provider integration, not tangled up with unrelated logic bugs — directly applying the "attribute before fixing" principle from the reverse-engineered judging model.

---

## PHASE 4 — TESTING STRATEGY

**Unit tests (per module, zero network):** `context_resolver` fixtures, `retrieval` candidate-filtering logic, `risk_scorer` hard-trigger rules, `personalization` lookups, `decision_engine` gate branches, `justification` template correctness.

**Integration tests:** full pipeline run against stubbed `perception`/`content_judgment`, on a small hand-picked subset (10–15 rows spanning personal/group/business/media) before the first full 110-row run.

**Regression tests (named, permanent, re-run before every submission):** `msg_110` (injection), `msg_040`/`msg_056` (muted+mention contrast pair), `msg_021`/`msg_022` (near-duplicate payment risk), all 8 domain-mismatch businesses.

**Hidden-test simulations:** construct 2–3 *synthetic* analogues of each named case above (same structural shape, different specific content) to confirm the system generalizes the pattern rather than memorizing the 4 known instances — directly addresses the Research Report's own Open Question #1.

**Failure injection:**
- Provider failure: force `perception`/`content_judgment` to raise, confirm the row still completes with a conservative default, not a crash.
- Malformed input: a `messages.csv` row with an unexpected null combination not seen in the confirmed 110 rows — confirm `context_resolver` logs loudly rather than silently defaulting.
- Empty dataset: run the orchestrator against a zero-row input, confirm it exits cleanly rather than erroring.
- Prompt injection: `msg_110`, already a named regression case — additionally test that the injected instruction text never appears verbatim, uncritiqued, in the generated `reason`.
- Media failure: a media file path that doesn't resolve — confirm `perception` degrades rather than crashing the whole batch.
- Scam/muted-group/business-impersonation cases: covered by the named regression suite above.

---

## PHASE 5 — EVALUATION STRATEGY + CHECKPOINTS

**Measurement approach (per ARCHITECTURE_DESIGN.md Phase 8):** run against all 30 `sample_messages.csv` rows, report `action`/`message_type` exact-match separately, spot-check `reason` for mechanism-specificity vs. genericness, check `confidence` distribution shape against the 0.78–0.91 reference band, verify every non-`none` `evidence_message_ids` entry against `message_history.csv` and the correct `user_id`, and check cross-row consistency on any structurally-similar row pairs.

**Checkpoints (run after every module milestone, not just at the end):**
1. After `context_resolver` + parallel lookup modules: confirm all 110 rows resolve without error — zero tolerance here.
2. After `decision_engine` (stubbed perception/content_judgment): run all 30 sample rows, expect partial accuracy (media/content-judgment rows will be wrong since they're stubbed) — the goal here is confirming the gate chain's *logic* is sound, not final accuracy.
3. After real `perception` wired in: re-run the same 30 sample rows, confirm the 23-media-row subset's accuracy specifically improved.
4. After real `content_judgment` wired in: re-run `msg_040`/`msg_056` specifically — this must now pass.
5. After `justification`: confirm zero contradiction-audit failures across all 30 sample rows.
6. After full `orchestrator` + full 110-row run: run the complete named regression suite (Phase 4) + the output-validation checks from ARCHITECTURE_DESIGN.md Phase 7.
7. Final, pre-submission: re-run checkpoint 6 one more time against the actual submission zip, extracted clean, per the Prompt Protocol's Submission Audit template.

---

## PHASE 6 — PROMPT PLAN

*Five prompts per module would be excessive — most modules need only planning + implementation + review. The higher-risk modules (`risk_scorer`, `content_judgment`, `decision_engine`) get the full five. All prompts assume the Universal Prefix from the Prompt Protocol is already prepended.*

### `context_resolver`
- **Planning:** "Given messages.csv's confirmed nullable FKs (group_id, business_id, sender_user_id), design ResolvedContext's shape so every nullable case is explicit, never silently defaulted."
- **Implementation:** "Implement context_resolver per the design above. No behavior beyond lookup — flag anything that looks like it needs a judgment call instead."

### `retrieval`
- **Planning:** "Design the candidate-filtering rule for retrieval: same user_id plus which secondary signals (sender, business, topic keyword)? Justify against the msg_021/msg_022 near-duplicate case specifically."
- **Implementation:** "Implement retrieval per the design. Every returned ID must be verified against message_history.csv before being returned — build that check in, not as an afterthought."

### `risk_scorer` (highest priority, full cycle)
- **Planning:** "List every hard-trigger rule needed to catch: msg_110's injection pattern, and all 8 domain-mismatch businesses by name. One rule per pattern, not one rule trying to catch everything."
- **Implementation:** "Implement the deterministic hard-triggers first, with a stubbed soft-score returning a fixed value. Do not wire the real soft-score model yet."
- **Review:** "Confirm: does any hard-trigger rule depend on the model call succeeding? It must not — walk through what happens if the soft-score call fails entirely."
- **Debug (if a named case fails):** "msg_110 didn't hard-trigger. Is this reproducible without any API call? Show me exactly which rule should have matched and why it didn't."
- **Optimization (only after correctness confirmed):** "Now wire in the real soft-score model call. Confirm all 8 hard-trigger tests still pass unchanged."

### `personalization`
- **Planning:** "Confirm which fields map to muted/opted-out/quiet-hours — cite the exact column names from group_members.csv and user_business_history.csv."
- **Implementation:** "Implement personalization per the design. Pure lookup, no model call anywhere in this module."

### `perception`
- **Planning:** "Design Observation's schema for both OCR and ASR outputs — what does content_judgment and risk_scorer actually need from each?"
- **Implementation:** "Implement perception against a stub client first that returns a fixed Observation. Real provider comes later."
- **Review:** "Confirm: does any failure mode here (timeout, malformed response, missing file) raise an exception instead of returning a degraded Observation? Fix any that do."

### `content_judgment` (full cycle)
- **Planning:** "Given msg_040 (generic_forward) and msg_056 (genuine_urgency) — both muted-group mentions — what's the minimal context digest this stage needs to tell them apart? Don't over-include fields."
- **Implementation:** "Implement content_judgment against a stub returning 'ambiguous' always, gated by decision_engine's gate-3 condition only."
- **Review:** "Confirm this is only ever invoked on gate-3, never on every row — show me the call site."
- **Debug (if msg_040/msg_056 fails post-real-model):** "Which one failed, and what did the model actually see as input? Is this a prompt problem or a genuinely hard case?"
- **Optimization:** "Now wire the real model call. Re-run msg_040/msg_056 plus the synthetic analogues from Phase 4. Report before/after."

### `decision_engine` (full cycle)
- **Planning:** "Confirm the 5-gate priority order from ARCHITECTURE_DESIGN.md Phase 5 exactly. Write one test per gate BEFORE implementing the gate itself."
- **Implementation:** "Implement decide() as a pure function. No import from perception, risk_scorer's model call, or content_judgment's model call — only their typed outputs."
- **Review:** "Walk through: if gate-1 and gate-3 conditions were both somehow true on the same row, which wins, and does the code actually enforce that, or just happen to produce the right answer today?"
- **Debug (if a sample row misroutes):** "Which gate fired, and was it the gate that should have fired? Attribute before proposing a fix."
- **Optimization:** "Are there any two gates whose conditions could both be satisfied ambiguously? Tighten the conditions so gate membership is mutually exclusive."

### `justification`
- **Planning:** "Confirm the confidence-band mapping (gate-1: 0.85-0.92, gate-3: 0.78-0.82, gate-4/5 clean: 0.83-0.89) against ARCHITECTURE_DESIGN.md Phase 5 exactly."
- **Implementation:** "Implement justify() as templates keyed only to (fired_gate, matched_rule_name, evidence_candidates). No free-text generation yet."
- **Review:** "Write the consistency-audit function now, even though templates make contradiction unlikely — and call it from justify(), not just define it."

### `orchestrator`
- **Planning:** "Design the per-row fault-isolation wrapper: what does a failed row's fallback output row look like exactly?"
- **Implementation:** "Implement run_batch() calling each module in sequence per ARCHITECTURE_DESIGN.md Phase 3's pipeline order."
- **Review:** "Confirm: does a single row's exception anywhere in the pipeline actually get caught, or does it propagate and kill the batch? Test this directly, don't assume."

---

## PHASE 7 — FAILURE PLAN

| Module | Most likely failure | Detection | Isolation | Recovery |
|---|---|---|---|---|
| `context_resolver` | unexpected null combination not in the 110 known rows | loud log on any unhandled FK shape | fails fast, single row | flag and inspect manually — should not need automatic recovery given confirmed data cleanliness |
| `retrieval` | over-broad candidate set for a generic sender | manual spot check against near-duplicate test cases | per-row, no cascading effect | tighten filter conditions |
| `risk_scorer` | a hard-trigger rule too narrow, misses a variant of a known pattern | named regression suite | per-row | add the missed variant as a new named test case, don't just patch silently |
| `personalization` | unlikely — pure lookup over clean data | unit test failure | per-row | fix lookup logic |
| `perception` | provider timeout/rate-limit/malformed response | try/except around the call, structured error logging | per-row | degrade to `failed=True` Observation, never crash |
| `content_judgment` | genuinely hard/ambiguous case, model gives an unexpected answer | named regression suite (msg_040/msg_056) + synthetic analogues | per-row | fall back to `ambiguous` → conservative `digest` |
| `decision_engine` | gate priority order violated by an edge case not yet tested | full branch-coverage test suite | none — this must never silently fail, treat any failure as P0 | add the missed case as a new gate test, fix logic, re-run full suite |
| `justification` | template doesn't cover a rare gate/rule combination | consistency-audit function | per-row | add missing template branch |
| `orchestrator` | one row's failure cascades to the batch | full dry run with intentional single-row failure injection | should never cascade — verify explicitly, don't assume the try/except is sufamplified | fix the specific uncaught exception path |

---

## PHASE 8 — SUBMISSION READINESS (measurable exit criteria)

- [ ] All 4 named regression cases (`msg_110`, `msg_040`/`msg_056`, `msg_021`/`msg_022`, all 8 domain-mismatch businesses) pass, verified by an actual test run this session, not assumed from a prior run.
- [ ] `output.csv` has exactly 110 rows, one per `message_id` in `messages.csv`, zero duplicates, zero missing IDs — verified by a direct set-comparison, not eyeballed.
- [ ] Header matches `message_id,action,message_type,reason,confidence,evidence_message_ids` byte-for-byte.
- [ ] Every `action` value is one of exactly 3 allowed values; every `message_type` is one of exactly 11 — verified by an enum-membership check across all 110 rows, not spot-checked.
- [ ] Confidence distribution: no row below 0 or above 1; overall shape is not bimodal at the extremes (spot check: what % of rows are ≥0.95 or ≤0.05 — should be a small minority, not the majority).
- [ ] Zero rows have a `reason` that is byte-identical to more than 2 other rows (the exact templated-justification check from a prior audit's `output_audit.py` logic) — genuine per-row diversity confirmed, not templated boilerplate.
- [ ] Every non-`none` `evidence_message_ids` entry verified to exist in `message_history.csv` AND belong to the correct `user_id` — 100% pass rate, not a sample.
- [ ] All deterministic modules (`context_resolver`, `retrieval`, `risk_scorer`'s hard-triggers, `personalization`, `decision_engine`, `justification`) have passing unit tests with zero skipped/pending tests remaining.
- [ ] `perception`/`content_judgment` sensitivity tests (blank-drop, swap) both pass.
- [ ] Full zip/repo extracted to a clean directory and the entrypoint run end-to-end, output observed directly — not assumed to still work because nothing was "supposed to" change.
- [ ] Interview prep document (Phase 9 below) is complete for every module, not just the ones that felt interesting to explain.

**When to stop improving:** once every checkbox above is true AND the last full run happened in the current session (not a stale run from hours earlier) — further polishing beyond this point has lower expected value than reserving time for interview prep and a final clean-environment verification pass.

---

## PHASE 9 — INTERVIEW MAPPING (per module)

### `context_resolver`
- **Likely question:** "How do you know every row resolves correctly?" **Tradeoff:** simplicity over defensive over-engineering, justified by confirmed 100% referential integrity from the research phase. **Ownership:** "I verified this directly against the dataset before writing any resolution logic, not after." **Limitation:** would need re-verification if the hidden test set has different FK-nullability patterns than the visible 110 rows.

### `retrieval`
- **Likely question:** "Why not embeddings for evidence retrieval?" **Tradeoff:** auditability and simplicity over paraphrase-catching recall, justified by the small corpus size (1,062 rows). **Ownership:** "I rejected embedding search explicitly — here's why it wasn't worth the added dependency at this scale." **Limitation:** will miss a heavily-paraphrased historical near-duplicate that shares no keywords with the current message.

### `risk_scorer`
- **Likely question:** "Why is the safety override hard-coded instead of left to the model?" **Tradeoff:** rigidity over flexibility, directly justified by `msg_110` proving the model can be argued out of an instructed rule. **Ownership:** "This is the one gate I made unconditional by construction, specifically because the problem statement itself states it must be unconditional." **Limitation:** only catches patterns explicitly enumerated; a genuinely novel scam phrasing not matching any hard-trigger falls through to the soft-score, which is probabilistic.

### `personalization`
- **Likely question:** "How is this different from just reading a settings table?" **Tradeoff:** none really — this module is deliberately simple. **Ownership:** "This is intentionally the least complex module in the system; every input is a stored fact, not a judgment call." **Limitation:** none significant.

### `perception`
- **Likely question:** "Why only 23 rows need this?" **Tradeoff:** targeted cost/latency over blanket processing. **Ownership:** "I confirmed this count directly from messages.csv's media_type column before deciding how much engineering effort this module deserved." **Limitation:** OCR/ASR quality is provider-dependent and untestable against hidden data in advance.

### `content_judgment`
- **Likely question:** "Why does this need a model at all — why not more rules?" **Tradeoff:** the single deliberate acceptance of non-determinism in the system, justified by the `msg_040`/`msg_056` pair specifically proving no rule set separates them. **Ownership:** "This is the one place I concluded determinism wasn't achievable, and I can show you the exact evidence that led to that conclusion." **Limitation:** genuinely probabilistic; the synthetic-analogue tests exist specifically to check generalization, not just memorization of the two known cases.

### `decision_engine`
- **Likely question:** "Walk me through your gate priority order and why it's ordered this way." **Tradeoff:** more upfront design rigor over a simpler single-LLM-call approach. **Ownership:** "Every gate's position in the chain is justified against a specific piece of evidence from the research phase — I can point to which finding justifies each gate's priority." **Limitation:** a genuinely novel conflict pattern not anticipated by the 5 gates would need a 6th gate added, not silently absorbed into an existing one.

### `justification`
- **Likely question:** "Why templates instead of an LLM writing the reason?" **Tradeoff:** slightly more mechanical prose over generation flexibility, in exchange for structural non-contradiction. **Ownership:** "A prior Orchestrate submission's exact, confirmed failure was a justification layer that could contradict its own decision — I built this specifically to make that failure mode structurally impossible here." **Limitation:** reason text style is closer to the labeled sample's terse style than to fully natural prose; explicitly acceptable per the frozen architecture's own reasoning.

### `orchestrator`
- **Likely question:** "What happens if the model provider goes down mid-run?" **Tradeoff:** per-row fault isolation over a simpler crash-on-error approach. **Ownership:** "I tested this directly by injecting a forced failure and confirming the batch completed with a degraded row instead of dying." **Limitation:** a degraded row still needs a human-legible flag in its `reason` field so it doesn't silently look like a confident, well-reasoned prediction.

---

## SUMMARY: what to build, when, how to verify, when to move on

1. **Hour 0–1:** `context_resolver`. Verify: all 110 rows resolve. Move on once zero-error.
2. **Hour 1–4:** `retrieval`, `risk_scorer` (deterministic half), `personalization`, in parallel. Verify: each module's unit tests green, `risk_scorer`'s 8+1 named cases pass. Move on once all three are green independently.
3. **Hour 4–7:** `decision_engine` against stubbed `perception`/`content_judgment`. Verify: full gate-branch test suite green, checkpoint 2 (Phase 5) run against 30 sample rows. Move on once branch coverage is complete, even if overall accuracy is still low due to stubs.
4. **Hour 7–10:** `perception` (stub → real), `justification`. Verify: checkpoint 3, consistency-audit passes. Move on once real perception is wired and the 23-media-row subset's accuracy visibly improves.
5. **Hour 10–13:** `content_judgment` (stub → real). Verify: checkpoint 4 — `msg_040`/`msg_056` specifically pass, plus synthetic analogues. **Do not move on until this specific pair passes** — it's the architecture's core bet.
6. **Hour 13–15:** `orchestrator`, full 110-row run. Verify: checkpoint 6, full named regression suite, all Phase 8 checkboxes.
7. **Hour 15–20:** iterate on any failing regression case, re-run full suite after each fix, do not touch unrelated modules while fixing one.
8. **Hour 20–22:** interview prep (Phase 9), README, transcript review.
9. **Hour 22–23:** clean-environment submission audit (checkpoint 7).
10. **Hour 23–24:** buffer, submit, stop touching it.

**When to stop improving, restated:** every Phase 8 checkbox true, verified this session, with time left over for interview prep — that combination is the actual finish line, not a feeling of "this could still be better."
