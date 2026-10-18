#!/usr/bin/env python3
"""
orchestrate_integration_kit / analyzers / gap_analyzer.py
============================================================
The core of the augmentation pivot. Takes:
  - repo_analysis.json  (from repo_analyzer.py — what's already there)
  - problem_ir.json      (from the Problem Analyzer prompt — what's needed)
and produces:
  - IMPLEMENTATION_PLAN.md
  - tasks.json (atomic, independently-executable units)

This is deliberately NOT trying to be clever about semantic matching --
matching "does existing file X implement decision gate Y" requires reading
code for meaning, which this script cannot safely automate. Instead it does
what's mechanically safe: enumerates every requirement from the IR, checks
for mechanically-detectable presence signals in the repo analysis (e.g. "is
there ANY file with a class/function whose name suggests this gate exists"),
and classifies each IR requirement as LIKELY_PRESENT, LIKELY_MISSING, or
NEEDS_HUMAN_REVIEW -- it refuses to silently guess when it isn't sure,
which is the same discipline the compiler enforces on IR validation.
"""

import argparse
import json
import re
from difflib import SequenceMatcher


def _fuzzy_present(name: str, candidates: list, threshold: float = 0.45) -> tuple:
    """Returns (best_match, score) — a soft, honest name-similarity check.
    Never claims certainty; the plan output always says 'likely', not 'confirmed'."""
    name_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    best, best_score = None, 0.0
    for c in candidates:
        c_tokens = set(re.findall(r"[a-z0-9]+", c.lower()))
        if not name_tokens or not c_tokens:
            continue
        overlap = len(name_tokens & c_tokens) / len(name_tokens | c_tokens)
        seq_score = SequenceMatcher(None, name.lower(), c.lower()).ratio()
        score = max(overlap, seq_score)
        if score > best_score:
            best, best_score = c, score
    return best, best_score


def analyze_gaps(repo_analysis: dict, problem_ir: dict) -> dict:
    all_symbol_names = []
    for fa in repo_analysis.get("file_analyses", []):
        for c in fa.get("classes", []):
            all_symbol_names.append(c["name"])
        for fn in fa.get("top_level_functions", []):
            all_symbol_names.append(fn["name"])
    all_file_paths = [fa["path"] for fa in repo_analysis.get("file_analyses", [])]

    gaps = {
        "decision_gates": [],
        "evidence_sources": [],
        "reference_sources": [],
        "output_fields": [],
        "critical_blockers": [],
    }

    # Critical blockers carry over verbatim — these ALWAYS block everything else
    for mi in repo_analysis.get("suspected_missing_local_imports", []):
        gaps["critical_blockers"].append(
            f"BLOCKER: `{mi['in_file']}` imports `{mi['missing_import']}`, which does not exist "
            f"in the repo. Nothing downstream of this file can be trusted to run until resolved."
        )
    for pe in repo_analysis.get("parse_errors", []):
        gaps["critical_blockers"].append(f"BLOCKER: `{pe['path']}` has a syntax error: {pe['parse_error']}")

    for gate in problem_ir.get("decision_gates", []):
        match, score = _fuzzy_present(gate["name"], all_symbol_names)
        status = "LIKELY_PRESENT" if score > 0.6 else ("NEEDS_HUMAN_REVIEW" if score > 0.3 else "LIKELY_MISSING")
        gaps["decision_gates"].append({
            "gate": gate["name"], "condition": gate["condition"],
            "status": status, "closest_repo_match": match, "match_confidence": round(score, 2),
        })

    for ev in problem_ir.get("evidence_sources", []):
        match, score = _fuzzy_present(ev["name"], all_symbol_names + all_file_paths)
        status = "LIKELY_PRESENT" if score > 0.6 else ("NEEDS_HUMAN_REVIEW" if score > 0.3 else "LIKELY_MISSING")
        gaps["evidence_sources"].append({
            "source": ev["name"], "modality": ev["modality"],
            "status": status, "closest_repo_match": match, "match_confidence": round(score, 2),
        })

    for rf in problem_ir.get("reference_sources", []):
        match, score = _fuzzy_present(rf["name"], all_symbol_names + all_file_paths)
        status = "LIKELY_PRESENT" if score > 0.6 else ("NEEDS_HUMAN_REVIEW" if score > 0.3 else "LIKELY_MISSING")
        gaps["reference_sources"].append({
            "source": rf["name"], "status": status,
            "closest_repo_match": match, "match_confidence": round(score, 2),
        })

    for of in problem_ir.get("output_schema", []):
        match, score = _fuzzy_present(of["name"], all_symbol_names)
        # output fields are usually just CSV columns/dict keys, not classes/functions --
        # low match confidence here is EXPECTED and not itself meaningful, flag as such
        gaps["output_fields"].append({
            "field": of["name"], "source": of["source"],
            "note": "Field presence in schema/output logic requires human review — "
                    "static symbol matching is unreliable for plain dict/CSV keys.",
        })

    no_tests = len(repo_analysis.get("test_files", [])) == 0
    gaps["testing_gap"] = "NO EXISTING TESTS FOUND — every task below must include writing tests, not just code." \
        if no_tests else f"{len(repo_analysis.get('test_files', []))} existing test file(s) found — extend, don't replace."

    return gaps


def compile_tasks(gaps: dict, problem_ir: dict) -> list:
    tasks = []
    tid = 1

    for blocker in gaps["critical_blockers"]:
        tasks.append({
            "id": f"T{tid:03d}", "priority": "P0-BLOCKER", "goal": blocker,
            "files": ["(identify from blocker message)"], "dependencies": [],
            "acceptance_criteria": "The named import resolves; `python -c 'import <module>'` succeeds.",
            "tests": "Run the repo's actual entrypoint end-to-end; it must not raise ImportError.",
            "expected_output": "Entrypoint runs without import errors.",
            "estimated_minutes": 30,
        })
        tid += 1

    for g in gaps["decision_gates"]:
        if g["status"] == "LIKELY_PRESENT":
            continue
        priority = "P1" if g["status"] == "LIKELY_MISSING" else "P2-VERIFY"
        tasks.append({
            "id": f"T{tid:03d}", "priority": priority,
            "goal": f"Implement/verify decision gate '{g['gate']}': {g['condition']}",
            "files": [g["closest_repo_match"] or "(new file in pipeline/decision.py)"],
            "dependencies": [],
            "acceptance_criteria": f"A pure function exists that evaluates: {g['condition']}, "
                                     f"with no import from perception/provider modules.",
            "tests": f"test_gate_{g['gate'].lower().replace(' ', '_')} — pass case + fail case, both asserted.",
            "expected_output": "New/modified test passes; gate is reachable from the main decision function.",
            "estimated_minutes": 45,
        })
        tid += 1

    for e in gaps["evidence_sources"]:
        if e["status"] == "LIKELY_PRESENT":
            continue
        priority = "P1" if e["status"] == "LIKELY_MISSING" else "P2-VERIFY"
        tasks.append({
            "id": f"T{tid:03d}", "priority": priority,
            "goal": f"Implement/verify perception handling for evidence source '{e['source']}' ({e['modality']})",
            "files": [e["closest_repo_match"] or "(new file in pipeline/perception.py)"],
            "dependencies": [],
            "acceptance_criteria": "Produces a typed Observation record; raw model output never reaches decision.py directly.",
            "tests": f"test_blank_drop_{e['source']}, test_swap_{e['source']}",
            "expected_output": "Sensitivity tests pass.",
            "estimated_minutes": 60,
        })
        tid += 1

    for r in gaps["reference_sources"]:
        if r["status"] == "LIKELY_PRESENT":
            continue
        priority = "P1" if r["status"] == "LIKELY_MISSING" else "P2-VERIFY"
        tasks.append({
            "id": f"T{tid:03d}", "priority": priority,
            "goal": f"Implement/verify firewalled reference lookup '{r['source']}'",
            "files": [r["closest_repo_match"] or "(new file in pipeline/reference.py)"],
            "dependencies": [],
            "acceptance_criteria": "Function signature cannot accept evidence/claim text as an argument.",
            "tests": "Static check: grep the function signature, confirm only the lookup key is accepted.",
            "expected_output": "Firewall confirmed structurally, not by convention.",
            "estimated_minutes": 30,
        })
        tid += 1

    if "NO EXISTING TESTS" in gaps["testing_gap"]:
        tasks.append({
            "id": f"T{tid:03d}", "priority": "P0-BLOCKER",
            "goal": "Establish a test suite before any further logic changes",
            "files": ["tests/"], "dependencies": [],
            "acceptance_criteria": "At least one test per decision gate exists and is runnable via pytest.",
            "tests": "pytest tests/ collects with zero errors (skips are fine, errors are not).",
            "expected_output": "`pytest tests/ -q` runs clean.",
            "estimated_minutes": 60,
        })
        tid += 1

    # sort P0 > P1 > P2 for the rendered plan, keep original relative order within tier
    priority_rank = {"P0-BLOCKER": 0, "P1": 1, "P2-VERIFY": 2}
    tasks.sort(key=lambda t: priority_rank.get(t["priority"], 9))
    return tasks


def render_plan_markdown(gaps: dict, tasks: list, problem_name: str) -> str:
    lines = [f"# IMPLEMENTATION_PLAN.md — {problem_name}", ""]

    if gaps["critical_blockers"]:
        lines.append("## 🛑 P0 Blockers — nothing else matters until these are fixed")
        for b in gaps["critical_blockers"]:
            lines.append(f"- {b}")
        lines.append("")

    lines.append(f"## Testing gap\n{gaps['testing_gap']}\n")

    lines.append("## Decision gates — status")
    lines.append("| Gate | Status | Closest repo match | Confidence |")
    lines.append("|---|---|---|---|")
    for g in gaps["decision_gates"]:
        lines.append(f"| {g['gate']} | {g['status']} | `{g['closest_repo_match'] or '-'}` | {g['match_confidence']} |")
    lines.append("")

    lines.append("## Evidence sources — status")
    lines.append("| Source | Status | Closest repo match | Confidence |")
    lines.append("|---|---|---|---|")
    for e in gaps["evidence_sources"]:
        lines.append(f"| {e['source']} | {e['status']} | `{e['closest_repo_match'] or '-'}` | {e['match_confidence']} |")
    lines.append("")

    lines.append("## Reference sources — status")
    lines.append("| Source | Status | Closest repo match | Confidence |")
    lines.append("|---|---|---|---|")
    for r in gaps["reference_sources"]:
        lines.append(f"| {r['source']} | {r['status']} | `{r['closest_repo_match'] or '-'}` | {r['match_confidence']} |")
    lines.append("")

    lines.append("## Output fields — REQUIRES HUMAN REVIEW (static matching unreliable here)")
    for of in gaps["output_fields"]:
        lines.append(f"- `{of['field']}` ({of['source']}) — {of['note']}")
    lines.append("")

    lines.append("## Atomic tasks (execute independently, in priority order)")
    for t in tasks:
        lines.append(f"### {t['id']} [{t['priority']}] {t['goal']}")
        lines.append(f"- **Files:** {', '.join(t['files'])}")
        lines.append(f"- **Dependencies:** {', '.join(t['dependencies']) or 'none'}")
        lines.append(f"- **Acceptance criteria:** {t['acceptance_criteria']}")
        lines.append(f"- **Tests:** {t['tests']}")
        lines.append(f"- **Expected output:** {t['expected_output']}")
        lines.append(f"- **Estimated time:** {t['estimated_minutes']} min")
        lines.append("")

    lines.append("## What should NOT change")
    lines.append("Anything marked LIKELY_PRESENT above. Re-implementing working, matched components")
    lines.append("burns time and, per the Orchestrate theory doc, actively hurts your Ownership score —")
    lines.append("touching code you don't need to touch is unjustifiable complexity. Verify with a quick")
    lines.append("read, don't rewrite by default.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-analysis", required=True, help="Path to repo_analysis.json")
    parser.add_argument("--problem-ir", required=True, help="Path to problem_ir.json")
    parser.add_argument("--out", default="IMPLEMENTATION_PLAN.md")
    parser.add_argument("--tasks-out", default="tasks.json")
    args = parser.parse_args()

    with open(args.repo_analysis) as f:
        repo_analysis = json.load(f)
    with open(args.problem_ir) as f:
        problem_ir = json.load(f)

    gaps = analyze_gaps(repo_analysis, problem_ir)
    tasks = compile_tasks(gaps, problem_ir)
    md = render_plan_markdown(gaps, tasks, problem_ir.get("problem_name", "Unnamed Problem"))

    with open(args.out, "w") as f:
        f.write(md)
    with open(args.tasks_out, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"Wrote {args.out} and {args.tasks_out} — {len(tasks)} atomic tasks generated")
    p0 = len([t for t in tasks if t["priority"] == "P0-BLOCKER"])
    if p0:
        print(f"WARNING: {p0} P0 blocker(s) — nothing else should be worked on first")


if __name__ == "__main__":
    main()
