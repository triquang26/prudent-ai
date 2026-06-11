"""E3 — multi-blocker VoI-plan scoring (reviewer-hardening node 6rb8dp).

The external review notes the VoI *ordering* is never exercised empirically: the
published acquisition experiment has a singleton blocking set. Here we mask BOTH
quality and cost on every RouterBench per-benchmark slice, so the blocking set
has two genuine members, and score the procedure's ranked acquisition plan by
reveal-until-decidable:

  - PLAN: follow the procedure's VoI/acqcost ranking; after each revealed axis,
    re-run right_size; stop at COMMIT. Record #measurements, cumulative
    acquisition cost (Appendix-B table), and whether the final commit is truly
    feasible + minimum-sufficient against ground truth.
  - RANDOM: reveal uniformly random axes (seeded, without replacement) until
    COMMIT; same records. This simulates measuring without an informative plan.
  - NECESSITY ablation: reveal only ONE of the two blockers (each alone) and
    check the query stays non-committed — i.e., both blockers are genuine.

Outputs: outputs/p5/multi_blocker.{json,md}

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_multi_blocker.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.solver.voi import ACQUISITION_COST
from prudent_ai.substrate import Substrate
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "E3-multi-blocker"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6

BIND = ("quality", "cost")
MASKED = frozenset({"quality", "cost"})


class MultiMaskedSubstrate:
    """Read-level mask over a SET of axes (extends the published 1-axis mask)."""

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
    """right_size with the masked axes minus *revealed* hidden."""
    regime = frozenset(ALL_AXES - (MASKED - revealed))
    hidden = MASKED - revealed
    s = MultiMaskedSubstrate(sub, frozenset(hidden)) if hidden else sub
    return right_size(s, q, KAPPA, PHI, regime)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)
    axes_order = sorted(ALL_AXES)

    per_query = []
    n_slices = 0
    skipped = []
    for bench in benches:
        bsub = BenchmarkSubstrate(sub, bench)
        if len(bsub.candidates("routerbench")) < MIN_CFG:
            skipped.append(bench)
            continue
        n_slices += 1
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        queries = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        for q in queries:
            # --- the abstention + its ranked plan (both axes hidden) ---
            rec0 = _commit_at(bsub, q, set())
            if rec0.action is Action.COMMIT:
                # not a multi-blocker instance (shouldn't happen); skip
                continue
            blockers = set(rec0.blocking_axes)
            plan = [av.axis for av in rec0.voi_ranking]

            # --- PLAN rollout: follow the ranked plan, re-ranking each step ---
            revealed: set[str] = set()
            plan_path: list[str] = []
            rec = rec0
            while rec.action is not Action.COMMIT and rec.voi_ranking:
                nxt = rec.voi_ranking[0].axis
                plan_path.append(nxt)
                revealed.add(nxt)
                rec = _commit_at(bsub, q, revealed)
            plan_n = len(plan_path)
            plan_cost = sum(ACQUISITION_COST.get(a, 1.0) for a in plan_path)
            plan_committed = rec.action is Action.COMMIT
            pred = rec.committed_config if plan_committed else None
            plan_feasible = bool(pred) and mp.true_feasible(q, pred)
            oc = mp.oracle_cost(q)
            pc = mp._true_val(pred, "cost") if pred else None
            plan_minsuff = (
                plan_feasible and oc is not None and pc is not None
                and abs(pc - oc) < 1e-12
            )

            # --- RANDOM rollout: uniform random axes until COMMIT ---
            order = axes_order[:]
            rng.shuffle(order)
            revealed = set()
            rnd_path: list[str] = []
            rec = rec0
            for ax in order:
                if rec.action is Action.COMMIT:
                    break
                rnd_path.append(ax)
                if ax in MASKED:
                    revealed.add(ax)
                rec = _commit_at(bsub, q, revealed)
            rnd_n = len(rnd_path)
            rnd_cost = sum(ACQUISITION_COST.get(a, 1.0) for a in rnd_path)
            rnd_committed = rec.action is Action.COMMIT

            # --- necessity ablation: each blocker alone must NOT suffice ---
            only_q = _commit_at(bsub, q, {"quality"}).action is Action.COMMIT
            only_c = _commit_at(bsub, q, {"cost"}).action is Action.COMMIT

            per_query.append({
                "benchmark": bench, "label": q.label,
                "blockers": sorted(blockers),
                "plan_first": plan[0] if plan else None,
                "plan_path": plan_path, "plan_n": plan_n,
                "plan_acqcost": round(plan_cost, 4),
                "plan_committed": plan_committed,
                "plan_feasible": plan_feasible,
                "plan_min_sufficient": plan_minsuff,
                "random_n": rnd_n, "random_acqcost": round(rnd_cost, 4),
                "random_committed": rnd_committed,
                "resolved_by_quality_alone": only_q,
                "resolved_by_cost_alone": only_c,
            })

    n = len(per_query)
    both_blockers = sum(1 for r in per_query
                        if set(r["blockers"]) >= {"quality", "cost"})
    plan_first_cost = sum(1 for r in per_query if r["plan_first"] == "cost")
    mean_plan_n = sum(r["plan_n"] for r in per_query) / n
    mean_rnd_n = sum(r["random_n"] for r in per_query) / n
    mean_plan_cost = sum(r["plan_acqcost"] for r in per_query) / n
    mean_rnd_cost = sum(r["random_acqcost"] for r in per_query) / n
    plan_ok = sum(1 for r in per_query
                  if r["plan_committed"] and r["plan_feasible"]
                  and r["plan_min_sufficient"])
    neither_alone = sum(1 for r in per_query
                        if not r["resolved_by_quality_alone"]
                        and not r["resolved_by_cost_alone"])

    res = {
        "metadata": {
            "provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
            "kappa": list(KAPPA), "seed": SEED, "pcts": list(PCTS),
            "bind": list(BIND), "masked": sorted(MASKED),
            "n_slices": n_slices, "skipped": skipped, "n_queries": n,
        },
        "summary": {
            "n": n,
            "blocking_set_contains_both": both_blockers,
            "neither_blocker_alone_resolves": neither_alone,
            "plan_names_cost_first": plan_first_cost,
            "mean_measurements_plan": round(mean_plan_n, 3),
            "mean_measurements_random": round(mean_rnd_n, 3),
            "mean_acqcost_plan": round(mean_plan_cost, 4),
            "mean_acqcost_random": round(mean_rnd_cost, 4),
            "plan_commit_feasible_minsuff": plan_ok,
        },
        "per_query": per_query,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "multi_blocker.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    s = res["summary"]
    lines = ["# E3 — multi-blocker VoI-plan scoring (mask quality AND cost)", ""]
    lines.append(f"- slices: {n_slices}; queries: {n}")
    lines.append(f"- blocking set contains both axes: {both_blockers}/{n}")
    lines.append(f"- neither blocker alone resolves: {neither_alone}/{n} "
                 "(both measurements genuinely necessary)")
    lines.append(f"- plan names cost first (VoI/acqcost): {plan_first_cost}/{n}")
    lines.append(f"- measurements to commit: plan {s['mean_measurements_plan']} "
                 f"vs random {s['mean_measurements_random']}")
    lines.append(f"- cumulative acquisition cost: plan {s['mean_acqcost_plan']} "
                 f"vs random {s['mean_acqcost_random']}")
    lines.append(f"- plan final commits feasible+min-sufficient: {plan_ok}/{n}")
    (OUT_DIR / "multi_blocker.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR/'multi_blocker.json'} and .md")


if __name__ == "__main__":
    main()
