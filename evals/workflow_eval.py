"""Moved to `evals/workflows/` in M5 (generate.py builds the labelled traces, run.py scores them).
Kept so older commands and ledger entries still run: this runs the current benchmark.

    cd services/api && uv run python ../../evals/workflows/run.py
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv[0] = str(Path(__file__).resolve().parent / "workflows" / "run.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
