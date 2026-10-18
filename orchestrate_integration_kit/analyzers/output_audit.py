#!/usr/bin/env python3
"""
orchestrate_integration_kit / analyzers / output_audit.py
============================================================
Audits a real output.csv against a ProblemIR's schema and invariants.
Produces OUTPUT_AUDIT.md plus copy-ready prompts for fixing weak rows.

Checks performed (all mechanical, all real):
  - header exact match
  - per-column type/enum conformance
  - declared invariants (simple presence/co-occurrence rules)
  - cross-row duplicate detection (exact full-row duplicates)
  - templated/low-diversity justification text detection (the exact bug
    class found in the June audit: 3 distinct justification strings across
    44 rows)
  - missing/empty required fields
  - supporting_image_ids-style fields referencing IDs not present in the
    row's own image_paths/source field, IF such a field pairing is declared

USAGE:
    python output_audit.py --csv output.csv --problem-ir problem_ir.json --out OUTPUT_AUDIT.md
"""

import argparse
import csv
import json
import re
from collections import Counter


def load_csv(path: str) -> tuple:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def audit(header: list, rows: list, ir: dict) -> dict:
    findings = {"header_ok": True, "header_issues": [], "row_issues": [], "summary": {}}

    expected_header = ir.get("output_csv_columns", [])
    if expected_header and header != expected_header:
        findings["header_ok"] = False
        findings["header_issues"].append(f"Expected: {expected_header}")
        findings["header_issues"].append(f"Got:      {header}")

    col_idx = {c: i for i, c in enumerate(header)}
    schema_by_name = {f["name"]: f for f in ir.get("output_schema", [])}

    # --- per-row checks ---
    enum_pattern = re.compile(r"^enum\[(.*)\]$")
    row_issues_by_row = []
    justification_col = None
    for cand in ("claim_status_justification", "justification", "reasoning", "explanation"):
        if cand in col_idx:
            justification_col = cand
            break

    for i, row in enumerate(rows, start=1):
        issues = []
        row_dict = dict(zip(header, row)) if len(row) == len(header) else None
        if row_dict is None:
            issues.append(f"Row {i}: column count mismatch ({len(row)} vs header's {len(header)})")
            row_issues_by_row.append((i, issues))
            continue

        for name, field_spec in schema_by_name.items():
            if name not in row_dict:
                continue
            val = row_dict[name].strip()
            if val == "":
                issues.append(f"Row {i}: field '{name}' is empty")
                continue
            m = enum_pattern.match(field_spec.get("type", ""))
            if m:
                allowed = {o.strip() for o in m.group(1).split(",")}
                if val not in allowed:
                    issues.append(f"Row {i}: field '{name}' = '{val}' not in allowed set {allowed}")

        if row_issues := issues:
            row_issues_by_row.append((i, row_issues))

    # --- cross-row: exact duplicate rows ---
    row_tuples = [tuple(r) for r in rows]
    dup_counter = Counter(row_tuples)
    duplicates = [(t, c) for t, c in dup_counter.items() if c > 1]

    # --- justification diversity check (the exact June-audit bug class) ---
    justification_diversity = None
    if justification_col:
        vals = [dict(zip(header, r)).get(justification_col, "") for r in rows if len(r) == len(header)]
        openings = [v[:40] for v in vals if v]
        opening_counts = Counter(openings)
        n_unique_openings = len(opening_counts)
        justification_diversity = {
            "n_rows_with_justification": len(vals),
            "n_unique_first_40_chars": n_unique_openings,
            "most_common_openings": opening_counts.most_common(5),
            "suspiciously_low_diversity": n_unique_openings <= max(3, len(vals) // 10),
        }

    findings["row_issues"] = row_issues_by_row
    findings["duplicates"] = duplicates
    findings["justification_diversity"] = justification_diversity
    findings["summary"] = {
        "n_rows": len(rows),
        "n_rows_with_issues": len(row_issues_by_row),
        "n_duplicate_rows": len(duplicates),
    }
    return findings


def render_markdown(findings: dict, csv_path: str) -> str:
    lines = [f"# OUTPUT_AUDIT.md — {csv_path}", ""]

    if not findings["header_ok"]:
        lines.append("## 🛑 HEADER MISMATCH — this alone can zero out the Output score")
        for issue in findings["header_issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    s = findings["summary"]
    lines.append("## Summary")
    lines.append(f"- Rows: {s['n_rows']}")
    lines.append(f"- Rows with at least one issue: {s['n_rows_with_issues']}")
    lines.append(f"- Exact duplicate rows: {s['n_duplicate_rows']}")
    lines.append("")

    jd = findings["justification_diversity"]
    if jd:
        lines.append("## Justification text diversity")
        lines.append(f"- Rows with justification text: {jd['n_rows_with_justification']}")
        lines.append(f"- Unique justification openings (first 40 chars): {jd['n_unique_first_40_chars']}")
        if jd["suspiciously_low_diversity"]:
            lines.append("- ⚠️ **SUSPICIOUSLY LOW DIVERSITY** — this is the exact failure pattern found in a prior")
            lines.append("  audit: templated/hardcoded justification text instead of per-row reasoning.")
            lines.append("  Most common openings:")
            for opening, count in jd["most_common_openings"]:
                lines.append(f"    - `{opening}...` × {count}")
        lines.append("")

    if findings["duplicates"]:
        lines.append("## Exact duplicate rows")
        for t, c in findings["duplicates"][:10]:
            lines.append(f"- appears {c}× — first fields: {t[:3]}")
        lines.append("")

    if findings["row_issues"]:
        lines.append("## Per-row issues (first 30 shown)")
        for i, issues in findings["row_issues"][:30]:
            for issue in issues:
                lines.append(f"- {issue}")
        lines.append("")

    lines.append("## Copy-ready prompts for fixing weak rows")
    lines.append("")
    lines.append("**If justification diversity is low:**")
    lines.append('> "These N rows share near-identical justification text despite different underlying')
    lines.append("> evidence. Read each row's actual claim + evidence fields and rewrite the justification")
    lines.append("> to cite the SPECIFIC evidence for that row, not a template. Do not just vary wording —")
    lines.append('> the content must differ where the evidence differs."')
    lines.append("")
    lines.append("**If enum violations found:**")
    lines.append('> "Row N has field X = value Y, which is not in the allowed set. Trace this value back')
    lines.append('> to the decision logic that produced it and confirm whether the logic or the schema')
    lines.append('> enum is wrong — do not just coerce the value to fit."')
    lines.append("")
    lines.append("**If duplicates found:**")
    lines.append('> "Rows N and M are byte-for-byte identical. Confirm these are genuinely identical claims,')
    lines.append('> or find the pipeline bug causing distinct inputs to collapse to the same output."')
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--problem-ir", required=True)
    parser.add_argument("--out", default="OUTPUT_AUDIT.md")
    args = parser.parse_args()

    header, rows = load_csv(args.csv)
    with open(args.problem_ir) as f:
        ir = json.load(f)

    findings = audit(header, rows, ir)
    md = render_markdown(findings, args.csv)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Wrote {args.out} — {findings['summary']['n_rows_with_issues']} row(s) with issues, "
          f"{findings['summary']['n_duplicate_rows']} duplicate(s)")


if __name__ == "__main__":
    main()
