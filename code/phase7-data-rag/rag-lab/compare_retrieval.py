"""Repeatable L64 comparison of ranking over one already authorized SQLite snapshot."""

import json
from pathlib import Path
import runpy
from statistics import median
from time import perf_counter

LAB = runpy.run_path(str(Path(__file__).resolve().with_name("lab.py")))
PUBLISHED = ("EXPORT-POLICY", 1, "§1")
OPERATIONS = ("EXPORT-OPS", 1, "§2")


def compare(*, repeats=20, timer=perf_counter):
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    cases = (
        ("expired", LAB["Query"](("过期", "重新生成"), (1.0, 0.0, 0.0)), OPERATIONS),
        ("retention", LAB["Query"](("留存", "期限"), (1.0, 0.0, 0.0)), PUBLISHED),
    )
    modes = ("lexical", "vector", "hybrid")
    rank = LAB["rank"]
    with LAB["open_demo"]() as db:
        pool = db.authorized("support", "mei")
        # Warm all modes before timing, keeping the pool, cases, and k fixed.
        observed = {mode: [rank(pool, query, mode=mode, k=1) for _, query, _ in cases] for mode in modes}
        samples = {mode: [] for mode in modes}
        for turn in range(repeats):
            # Rotate order to reduce a repeated first/last runner effect.
            offset = turn % len(modes)
            for mode in modes[offset:] + modes[:offset]:
                start = timer()
                for _, query, _ in cases:
                    rank(pool, query, mode=mode, k=1)
                samples[mode].append(timer() - start)
    return {
        "output_k": 1,
        "authorized_chunks": len(pool),
        "repeats": repeats,
        "modes": [
            {
                "mode": mode,
                "covered": sum(bool(hits and hits[0].chunk.key == gold)
                               for hits, (_, _, gold) in zip(observed[mode], cases, strict=True)),
                "cases": len(cases),
                "branch_candidate_scores_per_query": len(pool) * (2 if mode == "hybrid" else 1),
                "median_seconds_per_case_batch": median(samples[mode]),
            }
            for mode in modes
        ],
    }


if __name__ == "__main__":
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
