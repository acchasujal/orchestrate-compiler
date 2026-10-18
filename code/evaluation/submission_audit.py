"""Offline submission packaging audit; reports manual exclusions without mutating files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def audit_submission(repo_dir: Path, output_path: Path) -> dict[str, Any]:
    required = [
        "README.md", "problem_statement.md", "code/main.py", "code/evaluation/main.py",
        "dataset/messages.csv", "dataset/output.csv",
    ]
    missing = [path for path in required if not (repo_dir / path).is_file()]
    source_files = list((repo_dir / "code").rglob("*.py"))
    secret_patterns = [re.compile(r"AIza[0-9A-Za-z_-]{20,}"), re.compile(r"GEMINI_API_KEYS\s*=\s*[^$\n]+")]
    secret_hits = [str(path.relative_to(repo_dir)) for path in source_files if any(pattern.search(path.read_text(encoding="utf-8", errors="ignore")) for pattern in secret_patterns)]
    env_files = [str(path.relative_to(repo_dir)) for path in repo_dir.rglob(".env")]
    cache_dirs = [str(path.relative_to(repo_dir)) for path in repo_dir.rglob("__pycache__")]
    return {
        "passed": not missing and not secret_hits and not env_files and not cache_dirs,
        "missing_required_files": missing,
        "secret_hits_in_source": secret_hits,
        "env_files_to_exclude": env_files,
        "cache_dirs_to_exclude": cache_dirs,
        "output_exists": output_path.is_file(),
        "manual_steps": [
            "exclude .env files and __pycache__ directories from code.zip",
            "include the final chat transcript separately",
            "run one live Gemini startup check in a network-enabled environment",
        ],
    }
