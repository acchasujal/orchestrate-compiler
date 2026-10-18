# LOCAL_JUDGE.md
*Run this at hour 20 of the Competition Workflow, not hour 23 — leaves time to act. Score each axis 0–10 against the concrete check, not a vibe. This directly consumes the outputs of the other kit modules — it's not a separate opinion, it's a rollup.*

| Axis | Concrete check | Feeds from |
|---|---|---|
| **Repository integrity** | Does `python main.py --help` (or equivalent entrypoint) run without ImportError, right now, in a clean environment? | repo_analyzer.py's `suspected_missing_local_imports` — must be empty |
| **Gap closure** | What % of `tasks.json` P0/P1 tasks are actually done, verified against their stated acceptance criteria (not just "looks done")? | gap_analyzer.py output |
| **Output integrity** | Does `OUTPUT_AUDIT.md` show zero header mismatches, zero enum violations, and non-suspicious justification diversity? | output_audit.py |
| **Testing** | Is there ≥1 real (non-skipped) test per decision gate, written before the last live run? | tasks.json test fields |
| **Trust boundary discipline** | For every field classified `code_decided` in the Problem IR, can you point to the exact function that enforces it, with zero model call in its call path? | Problem IR + module 1 (Repository Understanding) |
| **Ownership ratio** | Pick 3 random files. Can you explain what each does and why, in under 30 seconds, without opening them? | self-test, no tool |
| **Operational realism** | Does the pipeline survive a simulated rate-limit kill mid-run and resume correctly? Actually kill it and check. | manual test |
| **Explainability** | Can you trace any single output field back through the pipeline to the exact rule/module that set it, in under 30 seconds? | module 11 (Error Analysis) |
| **Documentation** | Would a stranger reach a working run in under 5 minutes using only the README? | module 16 |
| **Interview readiness** | Have you run a full adversarial mock interview out loud, today, against THIS repo's actual state? | module 17 |

**Scoring guidance, calibrated to the reverse-engineered theory:**
- Repository integrity, Testing, Documentation, Explainability → these should reach 9–10 through discipline alone; treat anything below 8 here as a process failure, not bad luck, and fix it first.
- Output integrity, Operational realism → expect more natural variance; a 7 here driven by genuine model-perception noise is honest and defensible in interview. A 7 here driven by an unresolved P0 blocker is not — check which one it is.
- Interview readiness → treat as a hard gate. Below 8, do not submit until you've run the mock interview (module 17) at least once more.

**Any axis below 7 the night before submission is your highest-ROI remaining hour** — spend it there, ranked by lowest score first, not by what feels most interesting to fix.
