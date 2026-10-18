import sys
import os
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from code.app.orchestrator import ProviderStartupError, run_batch
from code.models import RuntimeConfig


if __name__ == "__main__":
    mode = os.getenv("ORCHESTRATE_PROVIDER_MODE", "real")
    try:
        report = run_batch(
            Path("dataset"),
            Path("dataset/output.csv"),
            RuntimeConfig(
                mode,
                Path(os.getenv("ORCHESTRATE_CACHE_DIR", "cache")),
                Path(os.getenv("ORCHESTRATE_JUDGMENT_CACHE_DIR", os.getenv("ORCHESTRATE_CACHE_DIR", "cache"))),
                int(os.getenv("ORCHESTRATE_MAX_RETRIES", "2")),
                True,
            ),
        )
    except ProviderStartupError as exc:
        print(f"STARTUP STOP: {exc}")
        raise SystemExit(2)
    print(report)
