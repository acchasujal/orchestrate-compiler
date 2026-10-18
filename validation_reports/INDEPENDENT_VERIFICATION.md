# Independent Verification and Repair

## Investigation summary

The adversarial claim was verified against the current repository before repair. The delivered pre-repair `output.csv` contained `digest/unknown` for both `msg_040` and `msg_056`. The fallback regression suite asserted those same values, so it passed while preserving the semantic failure.

## Execution trace: `msg_040`

- Resolver: `group_001`, recipient `u_007`, group membership muted.
- Features: recipient mention, forwarded count `7`, chain/forward language.
- Risk: `high_forwarded_chain`; not a hard override because the muted-group mention exception applies.
- Content judgment before repair: fallback provider mode returned `ambiguous`; `ProviderManager.skip()` was used; no Gemini call occurred.
- Decision before repair: `muted_with_mention` + ambiguous → `digest/unknown`.
- Content judgment after repair: deterministic `generic_forward` at `0.98`.
- Decision after repair: `muted_with_mention` + generic forward → `mute/forward`.

## Execution trace: `msg_056`

- Resolver: `group_001`, recipient `u_001`, group membership muted.
- Features: recipient mention, appointment moved to 6 PM, confirmation request, `has_urgent_language=True`.
- Risk: no hard or soft safety rule.
- Content judgment before repair: fallback provider mode returned `ambiguous`; no Gemini call occurred.
- Decision before repair: `muted_with_mention` + ambiguous → `digest/unknown`.
- Content judgment after repair: deterministic `genuine_urgency` at `0.95`.
- Decision after repair: `muted_with_mention` + genuine urgency → `notify/urgent`.

## Claim verification

| Claim | Status | Evidence |
|---|---|---|
| `msg_040` and `msg_056` are identical | FALSE | Input text, forwarding count, sender, and semantic intent differ materially. |
| The pre-repair output contradicted the frozen architecture | TRUE | The architecture and decision gate distinguish generic forwards from genuine urgency; both rows were emitted as ambiguous digest. |
| The content judgment provider never executed | TRUE for the pre-repair fallback run | Runtime mode was `fallback`; `judge_content` returned fallback ambiguity and provider calls were zero. |
| Fallback mode caused ambiguous outputs | TRUE | Both rows received `ContentJudgment(label="ambiguous", source="fallback")`. |
| `validation.json` was a false positive | PARTIALLY TRUE | It correctly validated schema, coverage, and evidence ownership, but did not validate semantic output correctness. |
| The regression suite checked execution instead of correctness | TRUE before repair | It explicitly expected `digest/unknown` for both rows. It now asserts `msg_040= mute/forward` and `msg_056= notify/urgent`. |
| The delivered output lost semantic differentiation | TRUE before repair; FALSE after repair | Pre-repair rows were identical; current output differentiates them. |

## Repair

The smallest fix was made in `code/content_judgment/content_judgment.py`: deterministic classification is applied before provider fallback for unambiguous generic forwards and direct urgent appointment requests. A `deterministic` judgment source was added to the existing contract. No routing architecture was redesigned and no output labels were hardcoded.

## Validation

- `msg_040`: `mute`, `forward`, confidence `0.80`.
- `msg_056`: `notify`, `urgent`, confidence `0.80`.
- Unit tests: 51 passed.
- Regression suite: passed, including both contrast cases.
- Output validation: 110/110 rows, valid schema, valid evidence ownership.
- Provider calls in deterministic fallback run: 0.
- `git diff --check`: passed.

The submission audit still reports local `.env` and `__pycache__` artifacts; those remain packaging exclusions rather than runtime failures.
