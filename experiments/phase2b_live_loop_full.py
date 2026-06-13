"""Phase 2b — live acquisition loop swept over the FULL RouterBench battery.

Scales the Phase-2 demo from 5 slices to all ~30 RouterBench per-benchmark slices
(~510 measurable-ground-truth decisions), in two masking settings, comparing the
VoI-ranked acquisition plan against random acquisition. Every measurement is real
(true value revealed into a scratch overlay, never the frozen db). Reports coverage,
the probes-to-commit distribution (plan vs random — the 2.0-vs-6.0 result at scale),
acquisition cost, hidden violations (must be 0), and minimum-sufficiency.

Random baseline: at each step reveal a uniformly-random axis from the measurable pool
{quality, cost, latency_p95, throughput, energy}; revealing an already-visible axis is a
no-op (the overlay only fills ⊥ cells), so random wastes probes until it happens to reveal
the masked blocker(s) — exactly the unplanned-probing cost the VoI plan avoids.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase2b_live_loop_full.py
Out:  outputs/phase2/live_loop_full.json
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.loop import LiveAcquisitionLoop
from prudent_ai.solver.beliefs import Phi, aggregate
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import Decidability, classify_query
from prudent_ai.substrate.substrate import Substrate
from prudent_ai.transfer.overlay import OverlayedSubstrate
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict, MaskedSubstrate

REPO = Path(__file__).parents[1]
DB = REPO / "data/apt_substrate.db"
OUT = REPO / "outputs/phase2/live_loop_full.json"
PCTS = tuple(range(10, 91, 5))          # 17 queries / slice
BIND = ("quality", "cost")
RANDOM_POOL = ("quality", "cost", "latency_p95", "throughput", "energy")
RANDOM_SEED = 7
MAX_PROBES = 8


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _oracle(bsub):
    def o(cid, axis):
        b = aggregate(bsub.cell(cid, axis), ("H",), Phi.POINT)
        return b.point if b.is_present else None
    return o


def _lcg(seed: int):
    """Tiny deterministic PRNG (avoids Math.random-style nondeterminism)."""
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state / 0x7FFFFFFF


def random_loop(masked, oracle, query, rng) -> int | None:
    """Reveal random axes from RANDOM_POOL until DECIDABLE; return probe count or None."""
    revealed: dict[tuple[str, str], tuple[float, float]] = {}
    order = list(RANDOM_POOL)
    # deterministic shuffle by the rng
    for i in range(len(order) - 1, 0, -1):
        j = int(next(rng) * (i + 1))
        order[i], order[j] = order[j], order[i]
    sub = OverlayedSubstrate(masked, revealed)
    res = classify_query(sub, query, kappa=("H", "M"), phi=Phi.INTERVAL)
    probes = 0
    for axis in order:
        if res.label is Decidability.DECIDABLE:
            return probes
        for cand in masked.candidates(query.tau):
            v = oracle(cand.id, axis)
            if v is not None:
                revealed[(cand.id, axis)] = (v, v)
        probes += 1
        sub = OverlayedSubstrate(masked, revealed)
        res = classify_query(sub, query, kappa=("H", "M"), phi=Phi.INTERVAL)
    return probes if res.label is Decidability.DECIDABLE else None


def run_setting(base, masked_axes: tuple[str, ...]) -> dict:
    benches = ValidationRunner(base).discover_routerbench_benchmarks()
    rng = _lcg(RANDOM_SEED)
    plan_probes, rnd_probes, costs = [], [], []
    n = n_commit = n_viol = n_minsuff = 0
    per_slice = []
    for bench in benches:
        bsub = BenchmarkSubstrate(base, bench)
        mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
        qs = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if not qs:
            continue
        masked = bsub
        for a in masked_axes:
            masked = MaskedSubstrate(masked, a)
        oracle = _oracle(bsub)
        loop = LiveAcquisitionLoop(oracle, max_probes=MAX_PROBES)
        s_commit = s_viol = s_minsuff = 0
        for q in qs:
            n += 1
            r = loop.run(masked, q)
            if r.action == "commit":
                n_commit += 1
                s_commit += 1
                plan_probes.append(len(r.probes))
                costs.append(r.acquisition_cost)
                viol = not mp.true_feasible(q, r.committed_config)
                if viol:
                    n_viol += 1
                    s_viol += 1
                else:
                    oc = mp.oracle_cost(q)
                    pc = aggregate(bsub.cell(r.committed_config, "cost"), ("H",), Phi.POINT)
                    if oc is not None and pc.is_present and abs(pc.point - oc) < 1e-9:
                        n_minsuff += 1
                        s_minsuff += 1
            rp = random_loop(masked, oracle, q, rng)
            if rp is not None:
                rnd_probes.append(rp)
        per_slice.append({"benchmark": bench, "n": len(qs), "commits": s_commit,
                          "violations": s_viol, "min_sufficient": s_minsuff})

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else 0.0
    return {
        "n_decisions": n,
        "coverage": round(n_commit / n, 4) if n else 0.0,
        "hidden_violations": n_viol,
        "min_sufficient_rate": round(n_minsuff / n_commit, 4) if n_commit else 0.0,
        "plan_mean_probes": mean(plan_probes),
        "random_mean_probes": mean(rnd_probes),
        "mean_acquisition_cost": mean(costs),
        "plan_probe_hist": dict(sorted(Counter(plan_probes).items())),
        "random_probe_hist": dict(sorted(Counter(rnd_probes).items())),
        "per_slice": per_slice,
    }


def main() -> None:
    md5_before = _md5(DB)
    base = CachedSubstrate(Substrate(str(DB)))
    settings = {
        "A_mask_quality": run_setting(base, ("quality",)),
        "B_mask_quality_cost": run_setting(base, ("quality", "cost")),
    }
    base.close()
    md5_after = _md5(DB)

    result = {
        "metadata": {"experiment": "phase2b_live_loop_full",
                     "pcts": list(PCTS), "random_pool": list(RANDOM_POOL),
                     "frozen_db_unchanged": md5_before == md5_after},
        "settings": settings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print(f"frozen_db_unchanged={md5_before == md5_after}")
    for name, s in settings.items():
        print(f"\n[{name}]  n={s['n_decisions']}  coverage={s['coverage']:.3f}  "
              f"hidden_violations={s['hidden_violations']}  "
              f"min_sufficient={s['min_sufficient_rate']:.3f}")
        print(f"  probes-to-commit: plan={s['plan_mean_probes']}  "
              f"random={s['random_mean_probes']}  (cost={s['mean_acquisition_cost']})")
        print(f"  plan hist={s['plan_probe_hist']}  random hist={s['random_probe_hist']}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
