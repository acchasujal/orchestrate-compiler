#!/usr/bin/env python3
"""
orchestrate_integration_kit / analyzers / repo_analyzer.py
============================================================
Scans an EXISTING repository (the one HackerRank hands you) and produces
REPOSITORY_ANALYSIS.md — a structured account of what's already there,
so the Gap Analyzer has something concrete to diff against the problem.

This is real static analysis, not a template: it walks the tree, parses
every .py file's AST, and extracts entrypoints, imports, classes,
functions, config-like constants, and existing tests. It flags (does not
guess) missing components and cross-file import structure, since that's
directly checkable without semantic understanding of the domain.

What this CANNOT do (and says so explicitly in its output): infer the
domain-level meaning of the code, or judge whether the existing
architecture is a good fit for the new problem. That's the Gap
Analyzer's job, and it needs the Problem IR to do it -- this script's
output is one of that step's two inputs.

USAGE:
    python repo_analyzer.py --repo /path/to/cloned/repo --out REPOSITORY_ANALYSIS.md
"""

import argparse
import ast
import json
import os
import re
import sys


CONFIG_LIKE_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*\s*=")
ENTRYPOINT_MARKERS = ('if __name__ == "__main__"', "if __name__ == '__main__'")


def find_py_files(repo_path: str) -> list:
    out = []
    skip_dirs = {".git", "__pycache__", "node_modules", "venv", ".venv", "env", ".mypy_cache"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return sorted(out)


def analyze_file(path: str, repo_path: str) -> dict:
    rel = os.path.relpath(path, repo_path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        tree = ast.parse(src, filename=rel)
    except SyntaxError as e:
        return {"path": rel, "parse_error": str(e)}

    imports, classes, functions, config_consts = [], [], [], []
    has_entrypoint = any(marker in src for marker in ENTRYPOINT_MARKERS)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, ast.ClassDef):
            bases = [ast.dump(b)[:40] for b in node.bases]
            is_model = any("BaseModel" in b or "dataclass" in ast.dump(node) for b in bases) or \
                       any(isinstance(d, ast.Name) and d.id == "dataclass" for d in node.decorator_list)
            classes.append({"name": node.name, "line": node.lineno, "looks_like_schema": is_model,
                             "docstring": (ast.get_docstring(node) or "")[:120]})
        elif isinstance(node, ast.FunctionDef) and isinstance(getattr(node, "parent", None), type(None)):
            pass  # handled via top-level scan below to avoid double-counting methods

    # top-level functions only (avoid class methods being miscounted as free functions)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append({"name": node.name, "line": node.lineno,
                               "docstring": (ast.get_docstring(node) or "")[:120],
                               "n_args": len(node.args.args)})
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if CONFIG_LIKE_PATTERN.match(f"{node.targets[0].id} ="):
                config_consts.append(node.targets[0].id)

    return {
        "path": rel,
        "n_lines": len(src.splitlines()),
        "imports": sorted(set(imports)),
        "classes": classes,
        "top_level_functions": functions,
        "config_constants": config_consts,
        "has_main_entrypoint": has_entrypoint,
        "is_test_file": "test" in os.path.basename(rel).lower(),
    }


def detect_missing_imports(file_analyses: list, repo_path: str) -> list:
    """Cross-check every local (relative-looking) import against files that actually
    exist. This directly targets the exact failure class found in the June audit
    (main.py importing two files that were never packaged)."""
    existing_modules = set()
    for fa in file_analyses:
        if "parse_error" in fa:
            continue
        mod_path = fa["path"][:-3].replace(os.sep, ".")
        existing_modules.add(mod_path)
        existing_modules.add(mod_path.split(".")[-1])

    missing = []
    for fa in file_analyses:
        if "parse_error" in fa:
            continue
        for imp in fa["imports"]:
            top = imp.split(".")[0]
            # only check imports that look like local package modules, skip stdlib/third-party guesses
            if imp.startswith("pipeline.") or imp.startswith(".") or (
                top not in ("os", "sys", "json", "re", "typing", "dataclasses", "enum",
                            "argparse", "collections", "itertools", "functools", "math",
                            "pydantic", "requests", "pandas", "numpy") and
                any(imp.startswith(m.split(".")[0] + ".") or imp == m for m in existing_modules)
                is False and "." in imp and not imp.split(".")[0].startswith("_")
            ):
                if imp not in existing_modules and not any(imp.startswith(m + ".") for m in existing_modules):
                    if imp.split(".")[0] in {p.replace(os.sep, ".").split(".")[0]
                                              for p in [os.path.dirname(fa2["path"]) for fa2 in file_analyses]}:
                        missing.append({"in_file": fa["path"], "missing_import": imp})
    return missing


def build_repo_analysis(repo_path: str) -> dict:
    py_files = find_py_files(repo_path)
    file_analyses = [analyze_file(p, repo_path) for p in py_files]

    entrypoints = [fa["path"] for fa in file_analyses if fa.get("has_main_entrypoint")]
    schema_files = [fa["path"] for fa in file_analyses
                     if any(c.get("looks_like_schema") for c in fa.get("classes", []))]
    test_files = [fa["path"] for fa in file_analyses if fa.get("is_test_file")]
    config_files = [fa["path"] for fa in file_analyses if fa.get("config_constants")]
    parse_errors = [fa for fa in file_analyses if "parse_error" in fa]

    # non-.py assets a judge/analyzer should know exist
    other_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for f in files:
            if f.lower() in ("readme.md", "requirements.txt", "pyproject.toml", "setup.py",
                              ".env.example", "agents.md", "claude.md"):
                other_files.append(os.path.relpath(os.path.join(root, f), repo_path))

    missing_imports = detect_missing_imports(file_analyses, repo_path)

    return {
        "repo_path": repo_path,
        "n_python_files": len(py_files),
        "entrypoints": entrypoints,
        "schema_like_files": schema_files,
        "test_files": test_files,
        "config_files": config_files,
        "notable_project_files": other_files,
        "parse_errors": parse_errors,
        "suspected_missing_local_imports": missing_imports,
        "file_analyses": file_analyses,
    }


def render_markdown(analysis: dict) -> str:
    a = analysis
    lines = [
        f"# REPOSITORY_ANALYSIS.md",
        f"*Auto-generated by repo_analyzer.py against `{a['repo_path']}`. This is what the",
        f"static analysis can determine mechanically. It does NOT know what the code is",
        f"FOR — that requires PROBLEM_IR.md and is the Gap Analyzer's job, not this one.*",
        "",
        f"## Summary",
        f"- Python files scanned: {a['n_python_files']}",
        f"- Entrypoints found (`if __name__ == \"__main__\"`): {len(a['entrypoints'])}",
        f"- Files that look like schema/data models: {len(a['schema_like_files'])}",
        f"- Existing test files: {len(a['test_files'])}",
        f"- Parse errors (syntax broken, cannot even import): {len(a['parse_errors'])}",
        f"- Suspected missing local imports (imports referencing modules not found in repo): {len(a['suspected_missing_local_imports'])}",
        "",
    ]

    if a["parse_errors"]:
        lines.append("## ⚠️ PARSE ERRORS — fix these first, nothing else can be trusted until these pass")
        for pe in a["parse_errors"]:
            lines.append(f"- `{pe['path']}`: {pe['parse_error']}")
        lines.append("")

    if a["suspected_missing_local_imports"]:
        lines.append("## ⚠️ SUSPECTED MISSING IMPORTS")
        lines.append("*Same failure class as: main.py importing files never packaged into the zip.*")
        for mi in a["suspected_missing_local_imports"]:
            lines.append(f"- `{mi['in_file']}` imports `{mi['missing_import']}` — not found anywhere in repo")
        lines.append("")

    lines.append("## Entrypoints")
    for e in a["entrypoints"]:
        lines.append(f"- `{e}`")
    lines.append("")

    lines.append("## Schema/data-model files")
    for s in a["schema_like_files"]:
        lines.append(f"- `{s}`")
    lines.append("")

    lines.append("## Existing tests")
    if a["test_files"]:
        for t in a["test_files"]:
            lines.append(f"- `{t}`")
    else:
        lines.append("- NONE FOUND. Task Compiler must include test-writing tasks before any logic changes.")
    lines.append("")

    lines.append("## Notable project files")
    for f in a["notable_project_files"]:
        lines.append(f"- `{f}`")
    lines.append("")

    lines.append("## File-by-file detail")
    for fa in a["file_analyses"]:
        if "parse_error" in fa:
            continue
        lines.append(f"### `{fa['path']}` ({fa['n_lines']} lines)")
        if fa["classes"]:
            lines.append("**Classes:**")
            for c in fa["classes"]:
                schema_tag = " `[schema-like]`" if c["looks_like_schema"] else ""
                lines.append(f"- `{c['name']}`{schema_tag} (line {c['line']}) — {c['docstring'] or '(no docstring)'}")
        if fa["top_level_functions"]:
            lines.append("**Top-level functions:**")
            for fn in fa["top_level_functions"]:
                lines.append(f"- `{fn['name']}({fn['n_args']} args)` (line {fn['line']}) — {fn['docstring'] or '(no docstring)'}")
        if fa["config_constants"]:
            lines.append(f"**Config-like constants:** {', '.join(fa['config_constants'])}")
        lines.append("")

    lines.append("## Trust boundaries — MANUAL REVIEW REQUIRED")
    lines.append("*Static analysis cannot determine which fields are model-sourced vs code-decided —*")
    lines.append("*that requires reading the actual logic. Use the 'Repository Understanding' prompt*")
    lines.append("*from PROMPT_LIBRARY.md with an LLM against the files above to fill this in before*")
    lines.append("*the Gap Analyzer runs.*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the cloned repository")
    parser.add_argument("--out", default="REPOSITORY_ANALYSIS.md")
    parser.add_argument("--json-out", default=None, help="Optional: also write raw analysis as JSON")
    args = parser.parse_args()

    if not os.path.isdir(args.repo):
        print(f"ERROR: {args.repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    analysis = build_repo_analysis(args.repo)
    md = render_markdown(analysis)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Wrote {args.out} ({len(md)} chars)")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"Wrote {args.json_out}")

    if analysis["parse_errors"]:
        print(f"WARNING: {len(analysis['parse_errors'])} file(s) have syntax errors", file=sys.stderr)
    if analysis["suspected_missing_local_imports"]:
        print(f"WARNING: {len(analysis['suspected_missing_local_imports'])} suspected missing import(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
