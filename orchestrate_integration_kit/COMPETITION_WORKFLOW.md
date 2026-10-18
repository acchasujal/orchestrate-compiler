# COMPETITION_WORKFLOW.md — Repository Augmentation Edition

| Hour | Step | Tool/Prompt | Exit criteria |
|---|---|---|---|
| 0:00–0:20 | `git clone` the HackerRank repo. Run `repo_analyzer.py --repo . --out REPOSITORY_ANALYSIS.md --json-out repo_analysis.json` immediately, before reading anything by eye. | `analyzers/repo_analyzer.py` | `REPOSITORY_ANALYSIS.md` exists; any parse errors or missing imports are visible immediately, not discovered at hour 20. |
| 0:20–1:00 | Read the problem statement + dataset sample. Fill in `problem_ir.json` using the Problem Analyzer frontend prompt (feed it PROBLEM_STATEMENT + DATASET_SAMPLE + API_DOCUMENTATION + SUBMISSION_RULES). | `ir.py` schema + frontend prompt | `problem_ir.json` exists and passes `ProblemIR.validate()` with zero errors. |
| 1:00–1:15 | Run `gap_analyzer.py --repo-analysis repo_analysis.json --problem-ir problem_ir.json`. | `analyzers/gap_analyzer.py` | `IMPLEMENTATION_PLAN.md` + `tasks.json` exist; P0 blockers (if any) are visible at the top. |
| 1:15–1:45 | Run PROMPT_LIBRARY.md #1 (Repository Understanding) against the actual flagged files, to add semantic judgment on top of the static gap analysis — especially any `NEEDS_HUMAN_REVIEW` entries. | prompt #1 | Every `NEEDS_HUMAN_REVIEW` row in `IMPLEMENTATION_PLAN.md` resolved to a human decision, recorded in `DECISIONS.md`. |
| 1:45–2:00 | Run PROMPT_LIBRARY.md #2 (Architecture Review) — confirm or reject the existing architecture's fit for the new problem, in writing. | prompt #2 | One paragraph in `DECISIONS.md` stating the decision and its named justification. |
| 2:00–2:30 | Fix any P0 blockers first, always, before anything else — even before full planning. | prompt #11 (Debugging) | `python <entrypoint> --help` runs with zero ImportError, verified live. |
| 2:30–3:00 | Sequence `tasks.json` for the day (prompt #3). | prompt #3 | Ordered task list with realistic time estimates, written down. |
| 3:00–8:00 | Work through P0/P1 tasks. Deterministic/logic tasks first (free to test), perception-touching tasks batched. Use prompt #4 or #5 per task depending on existing-file-match. | prompts #4, #5, #6 | Each task's stated acceptance criteria met and verified, not assumed. |
| 8:00–8:30 | Checkpoint/resume infrastructure in, if not already present in the repo (check `IMPLEMENTATION_PLAN.md`'s testing/operational gaps section). | manual + prompt #6 | A simulated kill-and-resume actually works, tested live. |
| 8:30–11:30 | Real perception integration, small subset first. Cache everything. | prompt #7, #8 | Cache hit-rate visible in logs; real cost/latency numbers exist, not $0.00 mock numbers. |
| 11:30–12:30 | Break. Re-read `DECISIONS.md` and the trust-boundary map from hour 1:15 — does the actual code still match it? | prompt #1 (re-run) | Any drift is caught and logged now, not discovered during the interview. |
| 12:30–15:00 | Full sample-set run. Attribute every wrong row (prompt #11), fix logic bugs immediately, batch perception issues. | prompt #11, #12 | Every wrong row has a one-line attribution in the log before any fix is attempted. |
| 15:00–16:00 | Run `output_audit.py`. Fix flagged rows using its generated prompts. | `analyzers/output_audit.py` | Zero header mismatches, zero enum violations, non-suspicious justification diversity. |
| 16:00–17:00 | Consolidate `DECISIONS.md` into a clean chronological record. | prompt #18 | Reads as real-time reasoning, not reconstructed hindsight. |
| 17:00–18:30 | Second full run + targeted re-tests on anything changed. | — | No regressions vs. the 12:30 run. |
| 18:30–20:00 | README (prompt #16). | prompt #16 | 5-minute-stranger-runnable, honest limitations section present. |
| 20:00–20:15 | Run `LOCAL_JUDGE.md`. Fix anything below 7, ranked by lowest score. | `LOCAL_JUDGE.md` | No axis below 7, or a named reason why not. |
| 20:15–21:30 | Run `interview_compiler.py` against the FINAL repo state, then a full adversarial mock interview out loud (prompt #17). | `interview_compiler.py`, prompt #17 | You can answer every generated follow-up without opening the code. |
| 21:30–22:30 | Final packaging. Extract the actual zip/repo to a clean directory, run the entrypoint from scratch. | Submission Checklist (below) | Verified this session, not assumed. |
| 22:30–23:30 | Buffer for whatever the 21:30 check found. | — | — |
| 23:30–24:00 | Submit. Stop touching it. | — | — |

## Submission Checklist
- [ ] Clean-clone (or clean-extract) and run the entrypoint end to end — verified this session.
- [ ] `repo_analyzer.py` re-run one final time; zero `suspected_missing_local_imports`, zero parse errors.
- [ ] `output_audit.py` re-run one final time; zero header/enum/duplicate issues.
- [ ] `DECISIONS.md` reads chronologically, not reconstructed.
- [ ] `INTERVIEW_PREP.md` regenerated against the FINAL repo state, not a mid-build snapshot.
- [ ] Every remaining `P0`/`P1` item in `tasks.json` is either done or explicitly, honestly disclosed as a known gap in the README and interview prep.
