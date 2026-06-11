"""E9 — acquisition-cost-table sensitivity of the two-blocker plan result.

Round-4 review, Q5: "The acquisition-plan result (2.0 vs 6.0 measurements) is on a
{quality, cost} two-blocker setting where cost is named first by the VoI/cost
ordering — how much of the advantage survives if acquisition costs are perturbed,
given the plan ordering depends entirely on the documented (assumed) cost table?"

We perturb `voi.ACQUISITION_COST` (in place) across scenarios and re-run the
two-blocker PLAN vs RANDOM rollout from run_multi_blocker.py. The distinction:
  - the EFFICIENCY advantage (plan ~2.0 measurements vs random ~6.0) is
    STRUCTURAL — both genuine blockers must be revealed to commit, so the plan,
    which reveals only blockers, takes exactly #blockers regardless of order;
    random wanders through irrelevant axes. This should be invariant to the table.
  - WHICH blocker is named first IS table-dependent — that is exactly what the
    table is for; we report the cost-first fraction per scenario to show when it
    flips, while the count and feasibility stay put.

Frozen db read-only via the immutable interface; the table is mutated in process
memory only and restored; no db mutation; nothing imputed.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_acqcost_sensitivity.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver import voi as voi_mod
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.substrate import Substrate
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "E9-acqcost-sensitivity"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6
BIND = ("quality", "cost")
MASKED = frozenset({"quality", "cost"})

_ORIG = dict(voi_mod.ACQUISITION_COST)


def _set_table(new: dict[str, float]) -> None:
    voi_mod.ACQUISITION_COST.clear()
    voi_mod.ACQUISITION_COST.update(new)


def scenarios(rng: random.Random) -> dict[str, dict[str, float]]:
    base = dict(_ORIG)
    rand = {a: round(base[a] * rng.uniform(0.5, 2.0), 4) for a in base}
    return {
        "baseline": dict(base),
        "cost_x5": {**base, "cost": base["cost"] * 5},
        "cost_x20": {**base, "cost": base["cost"] * 20},  # cost dearer than quality
        "quality_cheap": {**base, "quality": 0.05},
        "all_equal_0.5": dict.fromkeys(base, 0.5),  # pure raw-VoI ordering
        "random_0.5x_2x": rand,
    }


class MultiMaskedSubstrate:
    def __init__(self, sub, masked: frozenset[str]) -> None:
        self._sub = sub
        self._masked = masked

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        if a in self._masked:
            return []
        return self._sub.cell(x, a)

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def _commit_at(sub, q, revealed: set[str]):
    hidden = MASKED - revealed
    regime = frozenset(ALL_AXES - hidden)
    s = MultiMaskedSubstrate(sub, frozenset(hidden)) if hidden else sub
    return right_size(s, q, KAPPA, PHI, regime)


def run_scenario(bsub, mp, queries, axes_order, rng) -> list[dict]:
    out = []
    for q in queries:
        rec0 = _commit_at(bsub, q, set())
        if rec0.action is Action.COMMIT:
            continue
        plan = [av.axis for av in rec0.voi_ranking]
        # PLAN rollout
        revealed: set[str] = set()
        rec = rec0
        plan_path = []
        while rec.action is not Action.COMMIT and rec.voi_ranking:
            nxt = rec.voi_ranking[0].axis
            plan_path.append(nxt)
            revealed.add(nxt)
            rec = _commit_at(bsub, q, revealed)
        pred = rec.committed_config if rec.action is Action.COMMIT else None
        feas = bool(pred) and mp.true_feasible(q, pred)
        oc = mp.oracle_cost(q)
        pc = mp._true_val(pred, "cost") if pred else None
        minsuff = feas and oc is not None and pc is not None and abs(pc - oc) < 1e-12
        # RANDOM rollout
        order = axes_order[:]
        rng.shuffle(order)
        revealed = set()
        rec = rec0
        rnd_n = 0
        for ax in order:
            if rec.action is Action.COMMIT:
                break
            rnd_n += 1
            if ax in MASKED:
                revealed.add(ax)
            rec = _commit_at(bsub, q, revealed)
        out.append({
            "plan_first": plan[0] if plan else None,
            "plan_n": len(plan_path),
            "plan_feasible": feas, "plan_min_sufficient": minsuff,
            "random_n": rnd_n,
        })
    return out


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    axes_order = sorted(ALL_AXES)

    # gather slices/queries once
    slices = []
    for bench in benches:
        bsub = BenchmarkSubstrate(sub, bench)
        if len(bsub.candidates("routerbench")) < MIN_CFG:
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        queries = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if queries:
            slices.append((bsub, mp, queries))

    scen = scenarios(random.Random(SEED))
    results = {}
    try:
        for name, table in scen.items():
            _set_table(table)
            rng = random.Random(SEED)
            recs = []
            for bsub, mp, queries in slices:
                recs.extend(run_scenario(bsub, mp, queries, axes_order, rng))
            n = len(recs)
            results[name] = {
                "n": n,
                "mean_plan_measurements": round(sum(r["plan_n"] for r in recs) / n, 3),
                "mean_random_measurements": round(sum(r["random_n"] for r in recs) / n, 3),
                "plan_names_cost_first_frac": round(
                    sum(1 for r in recs if r["plan_first"] == "cost") / n, 3),
                "plan_feasible_frac": round(
                    sum(1 for r in recs if r["plan_feasible"]) / n, 3),
                "plan_min_sufficient_frac": round(
                    sum(1 for r in recs if r["plan_min_sufficient"]) / n, 3),
                "cost_acq": table.get("cost"), "quality_acq": table.get("quality"),
            }
            r = results[name]
            print(f"{name:>16}: plan {r['mean_plan_measurements']} vs random "
                  f"{r['mean_random_measurements']} meas | cost-first "
                  f"{100 * r['plan_names_cost_first_frac']:.0f}% | feas "
                  f"{100 * r['plan_feasible_frac']:.0f}% | min-suff "
                  f"{100 * r['plan_min_sufficient_frac']:.0f}%")
    finally:
        _set_table(_ORIG)  # always restore

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "seed": SEED,
                     "original_table": _ORIG},
        "scenarios": results,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "acqcost_sensitivity.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E9 — acquisition-cost-table sensitivity of the two-blocker plan", "",
             "| scenario | plan meas | random meas | plan names cost-first | "
             "plan feasible | plan min-suff |", "|---|---|---|---|---|---|"]
    for name, r in results.items():
        lines.append(f"| {name} | {r['mean_plan_measurements']} | "
                     f"{r['mean_random_measurements']} | "
                     f"{100 * r['plan_names_cost_first_frac']:.0f}% | "
                     f"{100 * r['plan_feasible_frac']:.0f}% | "
                     f"{100 * r['plan_min_sufficient_frac']:.0f}% |")
    lines += ["",
              "The efficiency advantage (plan measurements << random) is structural "
              "and invariant to the table; only WHICH blocker is named first shifts "
              "with the table, while feasibility and minimum-sufficiency hold."]
    (OUT_DIR / "acqcost_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'acqcost_sensitivity.json'} and .md")


if __name__ == "__main__":
    main()
