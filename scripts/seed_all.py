"""Seed the substrate from EVERY registered source — the one-command ingest.

Iterates `SOURCE_REGISTRY` (substrate/registry.py) sequentially (SQLite is a single
writer — never parallel) and prints a combined coverage report. Adding a new source
to the registry makes it appear here automatically; this script never needs editing.

    PYTHONNOUSERSITE=1 uv run python scripts/seed_all.py [--db ...] [--only bfcl,routerbench]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from prudent_ai.substrate.registry import SOURCE_REGISTRY, registry_by_name

AXES = [
    "quality", "latency_p95", "throughput", "cost",
    "energy", "memory_hw", "governance", "reviewer_burden",
]
DEFAULT_DB = "data/apt_substrate.db"


def coverage_report(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    print("\n" + "=" * 60)
    print("COMBINED COVERAGE (all registered sources)")
    print("=" * 60)
    print(f"{'axis':<18}{'obs':>8}{'populated':>12}")
    populated = 0
    for ax in AXES:
        n = conn.execute("SELECT COUNT(*) FROM observation WHERE axis=?", (ax,)).fetchone()[0]
        if n > 0:
            populated += 1
        print(f"{ax:<18}{n:>8}{('YES' if n else '⊥'):>12}")
    total = conn.execute("SELECT COUNT(*) FROM observation").fetchone()[0]
    cfgs = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
    srcs = conn.execute("SELECT COUNT(*) FROM source").fetchone()[0]
    print("-" * 60)
    print(f"{populated}/8 axes populated · {total} obs · {cfgs} configs · {srcs} sources")
    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the substrate from all registered sources")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--only", default="", help="comma-separated source names (default: all)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    specs = SOURCE_REGISTRY
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        by_name = registry_by_name()
        missing = want - set(by_name)
        if missing:
            raise SystemExit(f"unknown source(s): {sorted(missing)}; have {sorted(by_name)}")
        specs = [by_name[n] for n in want]

    print(f"Seeding {len(specs)} source(s) into {db_path} (idempotent):")
    for spec in specs:
        print(f"\n[{spec.name}] tau={spec.tau} axes={spec.axes} conf={spec.confidence}")
        report = spec.seed(db_path, verbose=not args.quiet)
        n = getattr(report, "observations_inserted", "?")
        print(f"  -> {n} observations")

    coverage_report(db_path)


if __name__ == "__main__":
    main()
