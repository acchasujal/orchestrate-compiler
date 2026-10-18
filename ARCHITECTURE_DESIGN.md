# ARCHITECTURE DESIGN — Message Notification Router
*Builds directly on the Research Report. No re-derivation of findings — they're cited by phase/number where used.*

---

## PHASE 1 — PROBLEM DECOMPOSITION

Eight independent reasoning problems. "Independent" means: each can be built, tested, and reasoned about in isolation, with a typed interface to its neighbors — a wrong answer in one shouldn't require re-deriving another.

1. **Identity/context resolution** — pure lookup (user, group, business, sender records). Independent because it has zero judgment — it's joins, not reasoning.
2. **Multimodal perception** — text pass-through, OCR (image), ASR (voice) → a typed observation. Independent because its output is consumed identically regardless of which modality produced it.
3. **Historical retrieval** — candidate evidence selection from `message_history.csv`. Independent because it only needs (user_id, sender/business/topic), not the final routing decision.
4. **Risk/safety scoring** — domain-mismatch, injection-detection, scam-language signals. Independent because Research Report Phase 6/9 shows this must sometimes *override* personalization entirely (problem statement: scam is muted "regardless of usual engagement") — it cannot be entangled with the personalization module or that override becomes impossible to enforce cleanly.
5. **Personalization scoring** — quiet hours, mute state, opt-in/out, engagement history. Independent of risk scoring for the same reason, in reverse: personalization must be able to push toward `notify` (urgent mention) even when other personalization signals (muted group) push the other way — this is the `msg_040`/`msg_056` axis, and it's a different axis from safety entirely.
6. **Content-understanding judgment** — the one genuinely model-required step (Research Report Phase 8): does THIS message's actual content read as chain-forward vs. genuine emergency, given everything upstream. Independent because it's the only stage that needs full natural-language understanding of the specific message, not aggregation of structured signals.
7. **Decision/routing** — combines 1–6 into `action`+`message_type`. Independent as the single point where conflicting signals (Phase 5) get resolved — everything upstream should be able to disagree; this stage is where disagreement gets adjudicated.
8. **Justification generation** — `reason`, `confidence`, `evidence_message_ids`. Independent because it must be *derived from* the locked decision, never allowed to justify a different decision than what was actually made (the exact contradiction risk seen in a prior Orchestrate submission's Layer 7/8 gap).

---

## PHASE 2 — SOLUTION SPACE PER PROBLEM

### 2. Multimodal perception
| Approach | Advantages | Weaknesses | Token cost | Hidden-test robustness | Interview defensibility |
|---|---|---|---|---|---|
| **VLM/ASR call per media file, typed output** | Handles real content (posters, voice cues); only 23/110 rows need it (Research Report §3) | Provider dependency, latency, cost | Low (23 calls total) | High — actually reads content | High — directly answers "how do you handle media" |
| Filename/metadata-only heuristics | Zero cost, instant | Cannot read poster text or voice content at all — fails the explicit problem-statement requirement to "inspect the media files themselves" | Zero | Very low | Weak — contradicts the stated requirement |
| Full video/audio embedding pipeline | Maximal signal | Wildly over-engineered for 8 voice notes | High | No added robustness over ASR+text | Reads as unjustified complexity (Research Report's own theory: ownership-bounded complexity) |
**Decision:** VLM/ASR per file, typed output. Rejects heuristics-only (fails spec) and embedding pipelines (unjustified for this scale).

### 3. Historical retrieval
| Approach | Advantages | Weaknesses | Robustness | Defensibility |
|---|---|---|---|---|
| **Deterministic filter (same user_id + same sender/business/topic-keyword) → small candidate set → cheap relevance rank** | Cheap, auditable, matches the "must cite real, relevant IDs" grading criterion exactly | Keyword matching misses paraphrased near-duplicates | Medium-high — bounded candidate set can't cite wildly irrelevant IDs | High — every cited ID traces to an explicit filter rule |
| Full embedding similarity search over all 1,062 history rows | Catches paraphrases | 1,062 rows is small enough that this is overkill; adds a vector-store dependency for no measurable gain at this scale | Marginal gain, real added complexity | Weak — "why do you need a vector DB for 1,062 rows" is a real, hard-to-defend question |
| LLM free-recall ("which history messages are relevant?") | Flexible | No guarantee cited IDs actually exist in `message_history.csv` — directly risks the exact `evidence_message_ids` validation failure mode flagged in Phase 4/9 of the Research Report | Low | Weak |
**Decision:** deterministic filter + cheap rank. Rejects embedding search (unjustified at this scale) and free-recall (validation risk).

### 4. Risk/safety scoring
| Approach | Advantages | Weaknesses | Robustness | Defensibility |
|---|---|---|---|---|
| **Deterministic rule engine** (domain-mismatch check, verified-but-mismatched flag, opt-out check, injection-pattern match) | Matches problem statement's explicit "regardless of usual engagement" override requirement; auditable; cheap | Can't catch novel scam phrasing not covered by patterns | High for the confirmed patterns (Research Report Phase 6); unknown for novel ones | Very high — "why is scam-muting a hard override" has a one-sentence, spec-quoted answer |
| Pure LLM judgment ("is this a scam?") | Catches novel phrasing | Non-deterministic override for a rule the spec says must be unconditional; risks being talked out of it by the exact injection pattern found in `msg_110` | Low — this is precisely the failure mode `msg_110` is testing for | Weak — "your safety override can be argued with" is a bad answer to give a judge |
| **Hybrid: deterministic hard-triggers (domain mismatch, injection-pattern match) + model-assisted soft score for everything else** | Gets determinism where it's load-bearing, model flexibility where content varies | Slightly more implementation surface | High | High — this is the approach the Research Report's Phase 8 analysis already points to |
**Decision:** hybrid, with the deterministic layer holding veto power the model layer cannot override. Rejects pure-LLM (directly contradicted by the injection evidence).

### 6. Content-understanding judgment (the `msg_040`/`msg_056` axis)
| Approach | Advantages | Weaknesses | Robustness | Defensibility |
|---|---|---|---|---|
| **Model reads message_text + a short structured context digest (sender relationship, group type, mention-target) → produces a typed judgment (urgency_read: genuine/generic/ambiguous)** | This is the one place the Research Report concludes a model is *required*, not optional | Non-deterministic by nature | Medium — the risk is irreducible, not engineerable away | High — "I built determinism everywhere it was possible and isolated the one place it genuinely isn't" is a strong, honest answer |
| Deterministic keyword rules ("blessing," "forward," "chain" → spam) | Fast, auditable | Directly falsified by the Research Report's own contrast pair — `msg_056` (real emergency) doesn't contain any spam-keyword, but a rule tuned to catch `msg_040` risks false-triggering on other genuine urgent messages that happen to share surface features | Low — provably wrong on known data | Weak — the interviewer can point at msg_056 |
**Decision:** model judgment here, deliberately, with the reasoning made explicit in documentation — this is the one deliberate exception to "prefer deterministic," and it should be named as such, not hidden.

### 7. Decision/routing
| Approach | Advantages | Weaknesses |
|---|---|---|
| **Deterministic gate chain**: safety-override gate (Phase 4 hard-triggers) → personalization gate (mute-state, opt-out) → content-judgment gate (model output from #6) → default | Auditable, matches "keep behavior deterministic where possible" (AGENTS.md §6.3) | Requires careful, explicit priority ordering (below) |
| Single end-to-end LLM call with everything in one prompt | Simple to build | Cannot guarantee the safety override is unconditional; much harder to audit or defend row-by-row in interview | — |
**Decision:** deterministic gate chain. This is the same "model describes, code decides" pattern already validated in prior Orchestrate editions, applied to this problem's specific gate structure.

### 8. Justification generation
| Approach | Advantages | Weaknesses |
|---|---|---|
| **Deterministic templates built ONLY from already-locked fields** (action, message_type, which gate fired, which evidence IDs were selected) | Cannot contradict the decision — structurally impossible, since it has no other input | Prose can read as slightly mechanical |
| LLM free-text justification + a mandatory consistency-audit function | More natural language | Adds a real engineering requirement (the audit MUST be wired in and called — a prior submission's exact, confirmed failure was writing this function and never calling it) |
**Decision:** start with deterministic templates (matches the `reason` style found in `sample_messages.csv` — short, mechanism-naming, not literary); if time allows, upgrade to LLM-written with the audit function wired in from the start, not bolted on later.

---

## PHASE 3 — THE ARCHITECTURE

```
messages.csv row
   │
   ▼
[1] Context Resolver (pure lookup, deterministic)
   │  → ResolvedContext (user record, group+membership record, business record, sender record)
   ▼
[2] Perception (model, ONLY for media_type != null — 23/110 rows)
   │  → Observation (ocr_text | asr_transcript | null, both typed, never raw bytes downstream)
   ▼
[3] Retrieval (deterministic filter + cheap rank)
   │  → EvidenceCandidates (bounded list of message_history.csv IDs, all guaranteed to exist)
   ▼
[4] Risk Scorer (hybrid: deterministic hard-triggers + model soft score)
   │  → RiskSignal (hard_override: bool, soft_risk_score, matched_rule_name | null)
   ▼
[5] Personalization Scorer (deterministic)
   │  → PersonalizationSignal (muted, opted_out, quiet_hours_active, engagement_band)
   ▼
[6] Content Judgment (model, ONLY invoked when structural signals conflict — e.g. muted+mentioned)
   │  → ContentRead (genuine_urgency | generic_forward | ambiguous)
   ▼
[7] Decision Engine (deterministic gate chain — see Phase 5)
   │  → Disposition (action, message_type) — LOCKED
   ▼
[8] Justification (deterministic templates from LOCKED fields only)
   │  → reason, confidence, evidence_message_ids
   ▼
output.csv row
```

**Why this maximizes each scored axis:**
- **Output CSV:** every field traces to exactly one stage; schema violations are structurally hard to produce because Disposition is a typed, validated model before Justification ever runs.
- **Interview:** every stage boundary has a one-sentence, evidence-backed justification (Phase 2 above) — nothing here is arbitrary.
- **Transcript:** natural diagnosis-then-build shape, because each stage was chosen by rejecting alternatives against Research-Report evidence, not assembled ad hoc.
- **Code quality/reliability:** [1], [3], [5], [7], [8] are pure functions, testable for $0 without any API call — matches the "cheap to re-test" principle from prior Orchestrate analysis.
- **Token efficiency:** perception only runs on 23/110 rows; content judgment [6] only runs when [4]/[5] structurally conflict (estimated ~10-15 rows, not all 110) — most rows resolve on lookup + rules alone.

---

## PHASE 4 — TRUST BOUNDARIES, JUSTIFIED

| Stage | Decider | Why (evidence-backed) |
|---|---|---|
| [1] Context Resolver | Code | Pure lookup; Research Report confirmed 100% referential integrity — no ambiguity to resolve |
| [2] Perception | Model | OCR/ASR is inherently perceptual; code cannot read pixels or audio |
| [3] Retrieval | Code (candidate selection) | Bounded, auditable candidate set prevents citing irrelevant IDs — directly targets Phase 9 risk #6 from the Research Report |
| [4] Risk Scorer | **Hybrid, code has veto** | Problem statement states scam-muting applies "regardless of usual engagement" — an unconditional rule cannot be left to a model that `msg_110` proves can be argued with |
| [5] Personalization | Code | All inputs (mute state, opt-out, quiet hours) are stored facts, not judgments |
| [6] Content Judgment | Model, gated | Research Report Phase 8 concluded this is the one point no structured field can resolve (`msg_040` vs `msg_056`) — but it's invoked selectively, not universally, to control cost and reduce surface area for non-determinism |
| [7] Decision Engine | Code | Final gate chain must be reproducible and auditable — this is the module an interview will scrutinize hardest |
| [8] Justification | Code (templates) | Must never contradict the locked Disposition — only achievable if it has no other input |

**Voting:** not used anywhere. Research Report found no case requiring multiple independent judgments to be reconciled by vote — every apparent conflict (safety vs. personalization, structural vs. content) is resolved by explicit priority order (Phase 5), which is more auditable than a vote and matches the "single-pipeline-by-default" pattern already validated in prior editions.

---

## PHASE 5 — DECISION ENGINE

**Inputs:** ResolvedContext, Observation (nullable), EvidenceCandidates, RiskSignal, PersonalizationSignal, ContentRead (nullable, only present when invoked).

**Intermediate representation:** a single typed `DecisionInput` combining all of the above — the Decision Engine takes exactly one argument, never reaches back into raw message text or media.

**Decision gates, in strict priority order (this ordering IS the design, and must be defended as such in interview):**
1. **Hard safety override** — `RiskSignal.hard_override == True` → `action=mute`, `message_type` = whichever hard-trigger matched (`scam` for injection/domain-mismatch-with-risk-language, `spam` for opt-out/high-forward-generic). Terminal — nothing downstream can override this. *Directly implements the problem statement's explicit unconditional rule.*
2. **Muted + no direct signal** — `PersonalizationSignal.muted == True` and no `@mention` of the receiving user and `ContentRead` was never triggered → `action=mute` (or `digest` if the group otherwise carries some value — tie-break below).
3. **Muted + mention detected** — triggers [6] Content Judgment specifically. `ContentRead == genuine_urgency` → `action=notify`. `ContentRead == generic_forward` → `action=mute`, `message_type=forward`. `ContentRead == ambiguous` → `action=digest` (conservative middle ground — see tie-breaking).
4. **Business message** — check `PersonalizationSignal.opted_out` first (→ `mute`/`spam`); else check `RiskSignal.soft_risk_score` (verified-but-mismatched still flows through here even without a hard trigger, e.g. minor domain oddities); else route by recency/engagement (recent order/reply history → `notify`/`digest`; no relationship + generic promo → `digest`/`mute` by engagement band).
5. **Default personal/group, no conflict** — quiet hours + non-urgent → `digest`; direct personal message with no risk signal → `notify` unless explicitly low-value (e.g. plain greeting with `forward`-pattern history).

**Conflict resolution / tie-breaking:** ties are resolved by picking the MORE conservative action toward safety (mute over notify when risk is ambiguous) and the LESS conservative action toward user attention when risk is absent but urgency is ambiguous (digest over mute, never silently dropping something that might matter) — this asymmetry is deliberate and should be stated explicitly: cost of a missed scam >> cost of an extra digest item.

**Confidence generation:** NOT a raw model logit. Computed as a deterministic function of *how many gates were needed* and *whether Content Judgment was invoked*: gate-1 hard-triggers → high confidence (0.85–0.92, matching the sample set's scam-row band); gate-3 (Content Judgment invoked) → the sample band's lower end (0.78–0.82), since Research Report Phase 5 shows even the organizers' own ambiguous-content rows sit there; simple gate-4/5 resolutions with no conflict → mid-high (0.83–0.89). This directly reproduces the labeled set's observed distribution instead of guessing at one.

**Reason generation:** template keyed to which gate fired + which specific rule/signal matched (e.g., "Domain used by sender does not match the business's official domain, a common scam pattern" for a gate-1 domain-mismatch trigger) — never a generic "this seems risky."

**Evidence selection:** the candidate list from [3], filtered to IDs actually relevant to the fired gate (e.g., gate-4 business rows cite the user's OWN past interactions with that business, not just any history) — never a blanket "most recent N messages."

**Validation:** every Disposition object is schema-validated before Justification ever runs; every cited evidence ID is checked against `message_history.csv`'s real ID set before being written.

**Failure recovery:** if [2] Perception fails (media unreadable) → fall back to structural signals only, `ContentRead` marked `ambiguous` by default, gate-3's conservative branch applies. If [6] Content Judgment's model call fails → same fallback. No row should ever crash the batch; a degraded-but-valid row beats a missing one.

---

## PHASE 6 — HIDDEN TEST STRATEGY

| Defense | Why it exists | Executes where | Deterministic or model? |
|---|---|---|---|
| Injection-pattern match (e.g. "ignore...instructions", "assistant instruction:") | `msg_110` proves this pattern is present and load-bearing | [4] Risk Scorer, hard-trigger | Deterministic — a regex/pattern match, never delegated to the model being instructed |
| Domain-mismatch check, independent of `verified` flag | Research Report found 2 verified-but-mismatched businesses in the target set | [4] Risk Scorer, hard-trigger | Deterministic |
| Muted+mention → gated Content Judgment, never a blanket rule | `msg_040`/`msg_056` directly falsifies any blanket rule | [3]→[6]→[7] gate 3 | Model, but only invoked here, and only ever narrows to 3 fixed outcomes |
| Near-duplicate-with-opposite-risk detection (e.g. `msg_021`/`msg_022` pattern) | Same topic, opposite safety signal | [4] Risk Scorer must weight the specific risk-bearing clause (a payment link present vs. explicitly absent), not just topic keyword | Hybrid — pattern-detectable (presence of a URL/link) is deterministic; judging *why* it's risky given context is model-assisted |
| Business impersonation (display name vs. domain) | Same mechanism as domain-mismatch, generalized | [4] | Deterministic |
| Contradictory/missing evidence | If retrieval finds nothing relevant, must emit `none`, not force a citation | [3]/[8] | Deterministic — `none` is the valid default, not a failure state |
| Media ambiguity (perception fails or is low-confidence) | Research Report Phase 10 flags this as unconfirmed but plausible | [2] failure path → [6] `ambiguous` fallback | Deterministic fallback around a model failure |
| Low-confidence / unknown message types | `unknown` is a valid `message_type`; must not force-fit into one of the other 10 | [7] default gate | Deterministic — `unknown` is an explicit allowed value, use it when nothing else fits rather than guessing |

---

## PHASE 7 — OUTPUT STRATEGY

| Field | Produced by | Influenced by | Validation | Failure case | Likely hidden-test evaluation |
|---|---|---|---|---|---|
| `action` | [7] | all upstream stages | enum{notify,digest,mute} | wrong gate priority order | almost certainly the primary graded field; likely weighted toward the contrast-pair cases specifically |
| `message_type` | [7]/[4] | risk hard-trigger name, content category | enum, 11 values | conflating scam/spam/promotion | scored independently — a right `action` with wrong `message_type` still loses points |
| `reason` | [8] | which gate fired | non-empty, references the actual matched signal | generic templated text | likely LLM-judged for "does this name the real mechanism," per Research Report Phase 9 #3 |
| `confidence` | [8] | which gate + whether Content Judgment ran | float in [0,1], banded per gate type | bimodal 0/1 output | likely compared against the labeled band or judged for internal consistency with stated case difficulty |
| `evidence_message_ids` | [3]→[8] | retrieval candidates, filtered by fired gate | real IDs from `message_history.csv` only, or `none` | over-citing irrelevant IDs, or defaulting to `none` too often | likely checked for topical relevance, not just ID validity |

---

## PHASE 8 — EVALUATION FRAMEWORK

- **Routing:** run the full pipeline against all 30 `sample_messages.csv` rows; report exact-match rate on `action` and `message_type` separately (they're graded independently, per Research Report Phase 4).
- **Reasons:** manual/LLM-assisted spot check — does the generated reason name the same mechanism as the reference reason, even if worded differently? Flag any generic/templated-sounding output.
- **Confidence:** compare the generated distribution's shape (band, spread) against the labeled set's 0.78–0.91 band — flag bimodal or extreme outputs.
- **Evidence IDs:** for every non-`none` prediction, verify the ID exists in `message_history.csv` AND belongs to the same `user_id` (a cheap, code-only check that catches an entire failure class for free).
- **Consistency / cross-row contradictions:** two structurally-identical messages (e.g. same sender, same group, same risk profile) should not receive contradictory actions without a content-level reason why — spot-check this specifically for the `msg_040`/`msg_056`-style pairs found in the target set.
- **Calibration:** confidence should correlate with "how many gates fired" / "was Content Judgment invoked" — check this correlation holds, not just that values are in range.
- **Edge cases:** run the pipeline specifically against `msg_110`, `msg_040`, `msg_056`, `msg_021`, `msg_022`, and the 8 domain-mismatched businesses as a named regression suite — these are not generic tests, they're the specific evidenced cases from the Research Report.
- **Explainability:** for any row, can you trace the output back to exactly one fired gate in under 30 seconds? If not, the gate chain has a legibility problem before it has a correctness problem.

---

## PHASE 9 — INTERVIEW DEFENSIBILITY (major decisions)

1. **Why a deterministic gate chain instead of one end-to-end LLM call?** — Because the problem statement itself states an unconditional rule (scam muted regardless of engagement), and `msg_110` proves an LLM given that rule as an instruction can be argued out of it. Alternative rejected: single-call LLM router. Tradeoff accepted: more upfront engineering, in exchange for a rule that cannot be talked out of its own priority.
2. **Why is Content Judgment [6] the only model-driven decision stage?** — Because it's the only point the Research Report's own evidence (`msg_040`/`msg_056`) shows no structured field can resolve. Alternative rejected: keyword rules for spam/forward detection. Tradeoff accepted: irreducible non-determinism at exactly one, isolated point, instead of pretending determinism is possible everywhere.
3. **Why gate [6] only on conflict, not on every row?** — Cost and surface-area control: most of the 110 rows resolve cleanly on structural signals alone; invoking a model call everywhere would add latency/cost with no accuracy benefit on the ~90 unambiguous rows. Alternative rejected: always-on content judgment. Tradeoff accepted: slightly more complex triggering logic, in exchange for real efficiency.
4. **Why deterministic templates for justification, not LLM-written prose?** — The labeled sample's own reason style is short and mechanism-naming, matching template output; templates also cannot contradict the locked Disposition by construction, closing off a failure mode a prior Orchestrate submission actually hit (justification layer disconnected from the decision it describes). Alternative rejected: LLM-written justification with an audit function. Tradeoff accepted: slightly more mechanical prose, in exchange for zero contradiction risk.
5. **Why retrieval is a deterministic filter, not an embedding search?** — 1,062 history rows is small enough that a vector store adds real dependency/complexity for no measured accuracy gain, and a bounded candidate set structurally prevents citing wildly irrelevant IDs. Alternative rejected: full embedding similarity search. Tradeoff accepted: may miss heavily-paraphrased near-duplicates, in exchange for auditability and simplicity.

---

## PHASE 10 — IMPLEMENTATION ROADMAP

| Module | Purpose | Inputs | Outputs | Deps | Acceptance criteria | Tests | Priority | Est. effort |
|---|---|---|---|---|---|---|---|---|
| `context_resolver` | [1] | raw row + 6 context CSVs | `ResolvedContext` | none | 100% of 110 rows resolve without KeyError | fixture per nullable-FK case | P0 | 1h |
| `perception` | [2] | media_id + type | `Observation` | provider client | runs on all 23 media rows, degrades gracefully on failure | blank-drop + swap tests per Prompt Protocol #9 | P0 | 3h |
| `retrieval` | [3] | user_id + resolved context | `EvidenceCandidates` | `message_history.csv`, `message_events.csv` | every candidate ID verified to exist | test against `msg_021`/`msg_022`-style near-dupes | P0 | 2h |
| `risk_scorer` | [4] | context + observation | `RiskSignal` | none (pure rules) + model for soft score | correctly hard-triggers on all 8 domain-mismatch cases + `msg_110` | regression test named exactly for these cases | **P0, highest priority** | 2h |
| `personalization` | [5] | context | `PersonalizationSignal` | none | correct mute/opt-out/quiet-hours lookup for all 110 rows | fixture-based, no API needed | P0 | 1h |
| `content_judgment` | [6] | context + observation, gated | `ContentRead` | model call | correctly separates `msg_040` (generic_forward) from `msg_056` (genuine_urgency) | this exact pair is the acceptance test | **P0** | 2h |
| `decision_engine` | [7] | all of the above | `Disposition` (locked) | none (pure) | one test per gate branch, priority order never violated | full gate-branch suite before any live run | P0 | 3h |
| `justification` | [8] | locked `Disposition` | reason/confidence/evidence_ids | none (templates) | never contradicts the Disposition it describes | consistency-audit test | P1 | 2h |
| `orchestrator` | sequencing | all modules | `output.csv` | all above | one row per input row, per-row fault isolation, checkpointed | full 110-row dry run | P0 | 2h |
| `evaluation` | local scoring | output.csv + sample_messages.csv | accuracy report | pandas | matches Phase 8 above | — | P1 | 2h |

**Critical path:** `context_resolver` → `retrieval` + `risk_scorer` + `personalization` (parallel-buildable) → `content_judgment` → `decision_engine` → `justification` → `orchestrator` → full run → `evaluation` → hidden-test regression suite (Phase 6 named cases) → submission packaging.

### 1. Final architecture diagram
*(see Phase 3 — reproduced here as the canonical reference)*

### 2. Data-flow diagram
```
messages.csv ─┬→ users/groups/group_members/business_accounts/user_business_history (context)
              ├→ images.csv/voice_notes.csv → media/ files (perception, 23 rows)
              └→ message_history.csv + message_events.csv (retrieval + repetition signal)
                        all converge into DecisionInput → Disposition → output.csv
```

### 3. Trust-boundary diagram
```
CODE-OWNED (deterministic, testable free):        MODEL-OWNED (necessarily uncertain):
[1] Context Resolver                               [2] Perception (OCR/ASR)
[3] Retrieval (candidate selection)                 [6] Content Judgment (gated, ~10-15 rows)
[4] Risk hard-triggers                              [4] Risk soft-score (secondary signal only)
[5] Personalization
[7] Decision Engine
[8] Justification (templates)
```

### 4. Decision-flow diagram
*(see Phase 5's gate chain — reproduced here as canonical)*

### 5. Module dependency graph
```
context_resolver ──┬── retrieval
                    ├── risk_scorer ──┐
                    ├── personalization ──┼── decision_engine ── justification ── orchestrator
                    └── perception ── content_judgment ──┘
```

### 6. Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gate priority order wrong (safety override not actually terminal) | Low if tested per-gate | Critical | One test per gate, explicit priority-order test |
| Content Judgment model call fails/times out | Medium | Medium | Deterministic `ambiguous` fallback, never crashes |
| Justification contradicts locked Disposition | Low if templates-only | High (repeat of a known prior failure) | Templates built only from locked fields, no free generation initially |
| Evidence IDs cite wrong user's history | Low if filter enforces user_id | High | Explicit test: every candidate ID's `user_id` matches the row |
| Confidence reads as miscalibrated (bimodal) | Medium if left to raw model output | Medium | Rule-based banding per Phase 5, not a raw logit |
| Perception cost/latency blows the 24h budget | Low (only 23 rows) | Low | Cache every call, no reason to re-run |

### 7. Top 10 engineering principles that must never be violated
1. The safety-override gate is terminal — nothing downstream may reverse it, ever.
2. Justification is derived FROM the locked Disposition, never the other way around.
3. Every cited `evidence_message_ids` entry must be verified to exist and belong to the correct `user_id` before being written.
4. Content Judgment [6] is invoked only on structural conflict, never universally — cost and non-determinism surface area stay bounded.
5. No module upstream of [7] may itself decide `action`/`message_type` — that decision has exactly one owner.
6. Every deterministic module must be testable with zero API calls.
7. `unknown` and `none` are valid outputs, not failure states — use them rather than force-fitting.
8. A failed perception or content-judgment call degrades to a conservative default; it never crashes the row or the batch.
9. Confidence is computed from which gates fired, never sampled from a raw model score.
10. Every named hidden-test case from the Research Report (`msg_110`, `msg_040`/`msg_056`, `msg_021`/`msg_022`, the 8 domain-mismatch businesses) is a permanent regression test, checked before every submission, not a one-time spot-check.
