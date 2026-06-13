"""Phase 2 — live acquisition loop demo (small, real, end-to-end).

Closes the selective procedure's loop for real on a few RouterBench slices: an
underdetermined masked query → VoI-rank blockers → acquire the top measurable axis (reveal
its measured ground-truth value into a scratch overlay, never the frozen db) → re-verdict
→ commit. Records probes-to-commit, acquisition cost, coverage, hidden violations (must be
0), and min-sufficiency. Also demonstrates that governance cannot be looped (raises).

Two settings on the SAME slices:
  (A) mask quality (1 genuine blocker)         → ~1 real probe to commit;
  (B) mask quality AND cost (2 genuine blockers) → ~2 real probes to commit
      (the simulated 2.0-vs-6.0 result, now closed with real measurement).

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase2_live_loop_demo.py
Out:  outputs/phase2/live_loop_demo.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.loop import LiveAcquisitionLoop, NoMeasurementPathError
from prudent_ai.solver.beliefs import Phi, aggregate
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.query import make_query
from prudent_ai.substrate.substrate import Substrate
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict, MaskedSubstrate

REPO = Path(__file__).parents[1]
DB = REPO / "data/apt_substrate.db"
OUT = REPO / "outputs/phase2/live_loop_demo.json"
N_SLICES = 5
PCTS = (30, 50, 70)
BIND = ("quality", "cost")


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _make_oracle(bsub):
    """oracle(config_id, axis) → true measured value from the UNMASKED slice substrate."""
    def oracle(cid: str, axis: str) -> float | None:
        b = aggregate(bsub.cell(cid, axis), ("H",), Phi.POINT)
        return b.point if b.is_present else None
    return oracle


def _run_setting(bsub, mp, queries, masked_axes: tuple[str, ...]) -> list[dict]:
    """Run the loop on each query with the given axes masked; score each outcome."""
    masked = bsub
    for a in masked_axes:
        masked = MaskedSubstrate(masked, a)
    oracle = _make_oracle(bsub)
    loop = LiveAcquisitionLoop(oracle)
    rows = []
    for q in queries:
        r = loop.run(masked, q)
        if r.action == "commit":
            r.hidden_violation = not mp.true_feasible(q, r.committed_config)
            oc = mp.oracle_cost(q)
            pc = aggregate(bsub.cell(r.committed_config, "cost"), ("H",), Phi.POINT)
            r.min_sufficient = (not r.hidden_violation and oc is not None
                                and pc.is_present and abs(pc.point - oc) < 1e-9)
        rows.append({
            "label": q.label, "action": r.action,
            "committed": r.committed_config, "probes": r.probes,
            "n_probes": len(r.probes), "acquisition_cost": r.acquisition_cost,
            "hidden_violation": r.hidden_violation, "min_sufficient": r.min_sufficient,
        })
    return rows


def _summarize(rows: list[dict]) -> dict:
    commits = [r for r in rows if r["action"] == "commit"]
    n = len(rows)
    return {
        "n_queries": n,
        "coverage": round(len(commits) / n, 4) if n else 0.0,
        "mean_probes_to_commit": round(
            sum(r["n_probes"] for r in commits) / len(commits), 3) if commits else 0.0,
        "mean_acquisition_cost": round(
            sum(r["acquisition_cost"] for r in commits) / len(commits), 4)
        if commits else 0.0,
        "hidden_violations": sum(1 for r in commits if r["hidden_violation"]),
        "min_sufficient_rate": round(
            sum(1 for r in commits if r["min_sufficient"]) / len(commits), 4)
        if commits else 0.0,
    }


def main() -> None:
    md5_before = _md5(DB)
    base = CachedSubstrate(Substrate(str(DB)))
    benches = ValidationRunner(base).discover_routerbench_benchmarks()

    slices = []
    setting_a_rows: list[dict] = []
    setting_b_rows: list[dict] = []
    for bench in benches:
        if len(slices) >= N_SLICES:
            break
        bsub = BenchmarkSubstrate(base, bench)
        mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
        qs = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if not qs:
            continue
        a_rows = _run_setting(bsub, mp, qs, ("quality",))
        b_rows = _run_setting(bsub, mp, qs, ("quality", "cost"))
        slices.append({"benchmark": bench, "n_queries": len(qs),
                       "A_mask_quality": _summarize(a_rows),
                       "B_mask_quality_cost": _summarize(b_rows)})
        setting_a_rows += a_rows
        setting_b_rows += b_rows

    # governance cannot be looped — must raise NoMeasurementPathError
    gov_bench = slices[0]["benchmark"]
    gov_bsub = BenchmarkSubstrate(base, gov_bench)
    gov_q = make_query("routerbench", [("governance", ">=", 1.0)], label="bind:governance")
    gov_masked = MaskedSubstrate(gov_bsub, "quality")
    loop = LiveAcquisitionLoop(_make_oracle(gov_bsub))
    try:
        loop.run(gov_masked, gov_q)
        gov_refused = False
    except NoMeasurementPathError:
        gov_refused = True

    md5_after = _md5(DB)
    result = {
        "metadata": {
            "experiment": "phase2_live_loop_demo",
            "n_slices": len(slices), "pcts": list(PCTS), "bind_axes": list(BIND),
            "frozen_db_unchanged": md5_before == md5_after,
            "governance_loop_refused": gov_refused,
        },
        "pooled": {
            "A_mask_quality": _summarize(setting_a_rows),
            "B_mask_quality_cost": _summarize(setting_b_rows),
        },
        "per_slice": slices,
    }
    base.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    pa, pb = result["pooled"]["A_mask_quality"], result["pooled"]["B_mask_quality_cost"]
    print(f"slices={len(slices)}  frozen_db_unchanged={md5_before == md5_after}  "
          f"governance_refused={gov_refused}")
    print(f"[A mask quality]      coverage={pa['coverage']:.2f} "
          f"probes={pa['mean_probes_to_commit']:.2f} cost={pa['mean_acquisition_cost']:.3f} "
          f"hidden_violations={pa['hidden_violations']} "
          f"min_sufficient={pa['min_sufficient_rate']:.2f}")
    print(f"[B mask quality+cost] coverage={pb['coverage']:.2f} "
          f"probes={pb['mean_probes_to_commit']:.2f} cost={pb['mean_acquisition_cost']:.3f} "
          f"hidden_violations={pb['hidden_violations']} "
          f"min_sufficient={pb['min_sufficient_rate']:.2f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
