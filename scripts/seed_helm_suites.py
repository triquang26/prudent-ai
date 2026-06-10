"""Batch-seed every HELM-family suite in helm_suite.SUITES (sequential, single writer).

Seeds all suites EXCEPT medhelm (already seeded) into the substrate, one at a time
(SQLite is a single writer — never parallelize). Resilient: a failing suite is logged
and skipped, the rest continue. Prints a per-suite + total coverage summary.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/seed_helm_suites.py [--only name1,name2]
"""

from __future__ import annotations

import argparse
import sys

from prudent_ai.substrate.helm_suite.seeder import SUITES, seed

DB_PATH = "data/apt_substrate.db"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated suite names")
    ap.add_argument("--skip", default="medhelm", help="comma-separated suite names to skip")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    skip = set(args.skip.split(",")) if args.skip else set()

    targets = [
        s.name for s in SUITES
        if (only is None or s.name in only) and s.name not in skip
    ]
    print(f"[batch] seeding {len(targets)} suites: {targets}", flush=True)

    results: dict[str, dict] = {}
    for name in targets:
        print(f"\n{'='*70}\n[seed] {name}\n{'='*70}", flush=True)
        try:
            rep = seed(db_path=DB_PATH, suite=name, verbose=False)
            results[name] = {
                "models": rep.models_seeded,
                "runs": rep.runs_fetched,
                "quality": rep.axes_coverage.get("quality", 0),
                "latency": rep.axes_coverage.get("latency_p95", 0),
                "offscale_skipped": sum(1 for e in rep.errors if "off-scale" in e),
            }
            print(f"[done] {name}: {results[name]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            results[name] = {"error": str(exc)[:120]}
            print(f"[FAIL] {name}: {exc}", file=sys.stderr, flush=True)

    print(f"\n{'='*70}\n[BATCH SUMMARY]\n{'='*70}", flush=True)
    tot_q = tot_l = 0
    for name, r in results.items():
        if "error" in r:
            print(f"  {name:<22} ERROR {r['error']}", flush=True)
        else:
            tot_q += r["quality"]
            tot_l += r["latency"]
            print(f"  {name:<22} models={r['models']:>4} q={r['quality']:>4} "
                  f"lat={r['latency']:>4} skipped={r['offscale_skipped']:>4}", flush=True)
    print(f"\n  TOTAL new quality obs={tot_q}, latency obs={tot_l}", flush=True)


if __name__ == "__main__":
    main()
