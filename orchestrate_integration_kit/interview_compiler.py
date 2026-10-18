#!/usr/bin/env python3
"""
orchestrate_integration_kit / interview_compiler.py
========================================================
Given the FINAL state of repo_analysis.json + problem_ir.json + tasks.json,
generates INTERVIEW_PREP.md. Pure codegen -- no judgment, so it cannot invent
your failure stories or your reasoning; it scaffolds the structure and pulls
in every real, checkable fact (trust boundaries, decision gates, task
completion status, P0 blockers if any remain) so nothing concrete is left
to memory. Fill in the bracketed sections yourself -- they require things
this script cannot know: what you actually found, tried, and learned.
"""

import argparse
import json


def generate(repo_analysis: dict, problem_ir: dict, tasks: list) -> str:
    gates_md = "\n".join(
        f"- **{g['name']}**: {g['condition']} -> pass: {g['on_pass']} / fail: {g['on_fail']}"
        for g in problem_ir.get("decision_gates", [])
    ) or "(none)"

    schema_md = "\n".join(
        f"| {f['name']} | {f['source']} | {f.get('invariant') or '-'} |"
        for f in problem_ir.get("output_schema", [])
    )

    done = [t for t in tasks if t.get("status") == "done"]
    remaining_p0 = [t for t in tasks if t["priority"] == "P0-BLOCKER" and t.get("status") != "done"]
    remaining_p1 = [t for t in tasks if t["priority"] == "P1" and t.get("status") != "done"]

    honesty_section = ""
    if remaining_p0:
        honesty_section += "### 🛑 Unresolved P0 blockers — you must be able to explain these if asked\n"
        for t in remaining_p0:
            honesty_section += f"- {t['goal']}\n"
    if remaining_p1:
        honesty_section += "\n### Unresolved P1 gaps\n"
        for t in remaining_p1:
            honesty_section += f"- {t['goal']}\n"
    if not honesty_section:
        honesty_section = "All P0/P1 tasks show status=done in tasks.json. Verify this is actually true, not just marked."

    return f"""# INTERVIEW_PREP.md — {problem_ir.get('problem_name', 'Unnamed')}
*Auto-generated from the FINAL repo state. Bracketed sections require your own input — this script cannot fabricate your reasoning or your bugs.*

## 30-second pitch
{problem_ir.get('one_line_success_criterion', '[fill in]')} — [state architecture in one clause] — [your proudest design choice].

## Trust boundary map (memorize)
| Field | Source | Invariant |
|---|---|---|
{schema_md}

## Decision gates — be ready to walk through each, in order
{gates_md}

## What was pre-existing in the repo vs. what you built
*This is a near-guaranteed interview question under the augmentation model — the judge will ask "what
was already here vs. what did you add," and a vague answer is a worse signal than a precise one.*
- Pre-existing, unmodified: [pull from IMPLEMENTATION_PLAN.md's "LIKELY_PRESENT, unchanged" entries]
- Pre-existing, extended: [pull from tasks with an existing `files` match]
- Newly built: [pull from tasks with "(new file...)" in `files`]

## Honest status at submission time
{honesty_section}

## Required prep before the interview (do not skip)
- [ ] At least one real, reproduced bug + fix, named specifically.
- [ ] For each decision gate above, the specific case that would break a rejected alternative design.
- [ ] Run PROMPT_LIBRARY.md's "Interview Preparation" prompt (#17) against the actual final repo, out loud.
- [ ] This honest-status section reviewed and is not stale relative to the actual final repo state.

## Likely follow-ups (regenerate, don't reuse a stale list)
Re-run PROMPT_LIBRARY.md prompt #17 against the FINAL repo after the last commit — a list generated
mid-build will be stale the moment the repo changes further.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-analysis", required=True)
    parser.add_argument("--problem-ir", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--out", default="INTERVIEW_PREP.md")
    args = parser.parse_args()

    with open(args.repo_analysis) as f:
        repo_analysis = json.load(f)
    with open(args.problem_ir) as f:
        problem_ir = json.load(f)
    with open(args.tasks) as f:
        tasks = json.load(f)

    md = generate(repo_analysis, problem_ir, tasks)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
