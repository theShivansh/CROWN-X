"""Workflow Learning Lite benchmark (docs/EVALUATION.md §6). Runs the deterministic miner over the
labelled scenarios from `generate.py` and reports:

- pattern precision and recall against the planted workflows;
- false-suggestion rate: suggestions that aren't a planted workflow, over all suggestions;
- support-count accuracy: planted workflows found with exactly their true support;
- determinism: the same stream, reversed and mined twice, gives byte-identical JSON.

Every false suggestion is listed with how often it occurred, for review by hand.

    cd services/api && uv run python ../../evals/workflows/run.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import scenario  # noqa: E402

from crownx.domain.workflow import mine  # noqa: E402


def main(seeds: int = 20) -> dict:
    true_positive = false_negative = support_exact = suggestions_total = 0
    false_seen: Counter[tuple[str, ...]] = Counter()
    deterministic = True
    for seed in range(seeds):
        events, planted = scenario(seed)
        mined = mine(events)
        dumped = json.dumps([s.model_dump() for s in mined], sort_keys=True)
        again = json.dumps([s.model_dump() for s in mine(list(reversed(events)))], sort_keys=True)
        deterministic &= dumped == again
        found = {tuple(s.steps): s for s in mined}
        suggestions_total += len(found)
        for steps, support in planted.items():
            if steps in found:
                true_positive += 1
                support_exact += found[steps].support == support
            else:
                false_negative += 1
        for steps in found:
            if steps not in planted:
                false_seen[steps] += 1
    false_positive = sum(false_seen.values())
    report = {
        "scenarios": seeds,
        "planted_workflows": true_positive + false_negative,
        "suggestions": suggestions_total,
        "pattern_precision": round(true_positive / max(1, true_positive + false_positive), 4),
        "pattern_recall": round(true_positive / max(1, true_positive + false_negative), 4),
        "false_suggestion_rate": round(false_positive / max(1, suggestions_total), 4),
        "support_count_accuracy": round(support_exact / max(1, true_positive), 4),
        "deterministic": deterministic,
        "false_suggestions": [
            {"steps": list(steps), "scenarios": count}
            for steps, count in sorted(false_seen.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    result = main()
    ok = result["deterministic"] and result["pattern_recall"] == 1.0
    sys.exit(0 if ok else 1)
