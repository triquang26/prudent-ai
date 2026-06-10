"""Seed the APT substrate with all P2 data sources sequentially.

Run with: PYTHONNOUSERSITE=1 uv run python scripts/seed_p2.py [--db data/apt_substrate.db]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from prudent_ai.substrate.bfcl.seeder import seed as bfcl_seed
from prudent_ai.substrate.helm_lite.seeder import seed as helm_seed
from prudent_ai.substrate.mlenergy.seeder import seed as mlenergy_seed
from prudent_ai.substrate.mlperf.seeder import seed as mlperf_seed

DEFAULT_DB = Path("data/apt_substrate.db")


def run(db_path: Path, verbose: bool = True) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("[1/4] HELM Lite (quality + latency_p95)")
    print("=" * 60)
    helm_seed(db_path, verbose=verbose)

    print()
    print("=" * 60)
    print("[2/4] BFCL (quality + cost + latency_p95)")
    print("=" * 60)
    bfcl_seed(db_path, verbose=verbose)

    print()
    print("=" * 60)
    print("[3/4] ML.ENERGY (energy + throughput + latency_p95)")
    print("=" * 60)
    mlenergy_seed(db_path, verbose=verbose)

    print()
    print("=" * 60)
    print("[4/4] MLPerf Inference v5.0 (throughput + latency_p95)")
    print("=" * 60)
    mlperf_seed(db_path, verbose=verbose)

    print()
    print("=" * 60)
    print("P2 SEED COMPLETE")
    print("=" * 60)

    import sqlite3
    conn = sqlite3.connect(db_path)
    print("\nFinal axis coverage:")
    axes = ["quality", "latency_p95", "throughput", "cost",
            "energy", "memory_hw", "governance", "reviewer_burden"]
    populated = 0
    for ax in axes:
        n = conn.execute("SELECT COUNT(*) FROM observation WHERE axis=?", (ax,)).fetchone()[0]
        flag = "YES" if n > 0 else "⊥"
        if n > 0:
            populated += 1
        print(f"  {ax:<22} {n:>6}   {flag}")
    print(f"\n{populated}/8 axes populated, {8 - populated}/8 ⊥")
    print(f"Total observations: {conn.execute('SELECT COUNT(*) FROM observation').fetchone()[0]}")
    print(f"Total configs:      {conn.execute('SELECT COUNT(*) FROM config').fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    run(Path(args.db), verbose=not args.quiet)
