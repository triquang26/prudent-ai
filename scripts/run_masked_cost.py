"""E1 — masked-COST validation battery (reviewer-hardening node 6rb8dp).

The published battery masks QUALITY. The external review asks for the Section-5
bridge: cost is the decidability map's #1 blocker (1,289 of 1,716 queries), so
what happens when the *objective* axis is the hidden one?

Design (mirrors run_p5_scaled.py exactly, except bind/mask):
  - every RouterBench per-benchmark slice (BenchmarkSubstrate, 11 cost-comparable
    models), auto-discovered from the substrate (C7);
  - bind (quality >= q_p AND cost <= c_p) at matched percentiles p in 10..90
    step 5 (17 queries/slice); MASK cost at the read level;
  - run ALL_RULES; score against the true (full-regime) measured values.

What the lattice can and cannot do here, stated up front:
  - B2/B3/B6 rank by *visible* cost; with cost masked their objective is
    unobservable, so they return no answer (coverage 0) — the honest finding is
    that current practice DEGENERATES, it does not silently violate. (B3's
    constant median fill cannot rank either — a constant orders nothing.)
  - The de-facto practitioner fallback is the leaderboard: B1 argmax-quality.
    B1 commits on every query; it hidden-violates the budget cap whenever the
    top-quality model costs more than c_p.
  - selective ABSTAINs (cost is blocking) and names cost via acquire_next; the
    end-to-end pipeline (measure cost -> re-run unmasked) must then commit the
    true min-cost feasible config.

Outputs: outputs/p5/masked_cost.{json,md}. Frozen db read-only via the solver
interface; seeded; no imputation of bottom.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_masked_cost.py
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
from prudent_ai.substrate import Substrate
from prudent_ai.validation.baselines import ALL_RULES
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "E1-masked-cost"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6

BIND = ("quality", "cost")
MASK = "cost"
_RULE_ORDER = [r.name for r in ALL_RULES]


def _selective_pipeline_per_query(mp: MaskAndPredict, sub, queries) -> list[dict]:
    """Per-query outcome of the END-TO-END pipeline: abstain -> measure the named
    axis -> re-run with it visible -> commit; scored against the full-regime truth.

    Mirrors the published scale_v2 construction for masked quality.
    """
    out = []
    visible = ALL_AXES - {MASK}
    for q in queries:
        rec = right_size(sub_masked(sub), q, KAPPA, PHI, visible)
        named = rec.acquire_next if rec.action is Action.ABSTAIN else None
        if rec.action is Action.COMMIT:
            pred = rec.committed_config
        else:
            # acting on the named measurement: reveal it, re-run at full regime
            regime2 = visible | ({named} if named else set())
            rec2 = right_size(sub, q, KAPPA, PHI, regime2)
            pred = rec2.committed_config if rec2.action is Action.COMMIT else None
        committed = pred is not None
        violated = committed and not mp.true_feasible(q, pred)
        # min-sufficiency: true cost equals oracle min-cost feasible
        minsuff = False
        if committed and not violated:
            oc = mp.oracle_cost(q)
            pc = mp._true_val(pred, "cost")
            minsuff = oc is not None and pc is not None and abs(pc - oc) < 1e-12
        out.append({
            "committed": committed, "hidden_violation": violated,
            "named_axis": named, "min_sufficient": minsuff,
        })
    return out


def sub_masked(sub):
    from prudent_ai.validation.harness import MaskedSubstrate
    return MaskedSubstrate(sub, MASK)


def _cluster_bootstrap_gap(per_slice: list[tuple[int, int]], rng, n_boot=10000):
    """Slice-clustered bootstrap CI of the pooled B1 hidden-violation rate."""
    k = len(per_slice)
    stats = []
    for _ in range(n_boot):
        samp = [per_slice[rng.randrange(k)] for _ in range(k)]
        nq = sum(s[0] for s in samp)
        nv = sum(s[1] for s in samp)
        stats.append(nv / nq if nq else 0.0)
    stats.sort()
    return stats[int(0.025 * n_boot)], stats[min(n_boot - 1, int(0.975 * n_boot))]


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)

    slices_out: dict[str, dict] = {}
    pooled_b1_pq: list[dict] = []
    pooled_pipe_pq: list[dict] = []
    per_slice_b1: list[tuple[int, int]] = []  # (n_queries, n_b1_violations)
    named_counts: dict[str, int] = {}
    n_pipe_commit_ok = 0
    n_pipe_total = 0
    skipped: list[str] = []

    for bench in benches:
        key = f"routerbench[{bench}]/bind=quality+cost/mask=cost"
        bsub = BenchmarkSubstrate(sub, bench)
        n_cand = len(bsub.candidates("routerbench"))
        if n_cand < MIN_CFG:
            skipped.append(key)
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        queries = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if not queries:
            skipped.append(key)
            continue
        report = mp.run(ALL_RULES, "routerbench", BIND, MASK, queries=queries)
        rules = report.rules

        b1 = next(r for r in ALL_RULES if r.name == "B1_accuracy_only")
        b1_pq = mp.score_rule_per_query(b1, queries, MASK)
        pipe_pq = _selective_pipeline_per_query(mp, bsub, queries)

        pooled_b1_pq.extend(b1_pq)
        pooled_pipe_pq.extend(pipe_pq)
        per_slice_b1.append(
            (len(b1_pq), sum(int(x["hidden_violation"]) for x in b1_pq)))
        for x in pipe_pq:
            if x["named_axis"]:
                named_counts[x["named_axis"]] = \
                    named_counts.get(x["named_axis"], 0) + 1
            n_pipe_total += 1
            if x["committed"] and not x["hidden_violation"] and x["min_sufficient"]:
                n_pipe_commit_ok += 1

        slices_out[key] = {
            "meta": {
                "benchmark": bench, "confidence": "H",
                "bind_axes": list(BIND), "masked_axis": MASK,
                "n_queries": len(queries), "n_candidates": n_cand,
                "b1_hidden_violation_rate":
                    rules["B1_accuracy_only"]["hidden_violation_rate"],
                "b1_coverage": rules["B1_accuracy_only"]["coverage"],
                "b2_coverage": rules["B2_observed_pareto"]["coverage"],
                "b3_coverage": rules["B3_imputation"]["coverage"],
                "b6_coverage": rules["B6_cost_accuracy"]["coverage"],
                "selective_coverage": rules["selective"]["coverage"],
                "oracle_hvr": rules["B5_oracle"]["hidden_violation_rate"],
            },
            "rules": rules,
        }

    # pooled inference: B1 vs pipeline at equal final coverage
    sig = ValidationRunner._paired_significance(pooled_b1_pq, pooled_pipe_pq, rng)
    n = len(pooled_b1_pq)
    b1_hv = sum(int(x["hidden_violation"]) for x in pooled_b1_pq) / n
    pipe_hv = sum(int(x["hidden_violation"]) for x in pooled_pipe_pq) / n
    pipe_cov = sum(int(x["committed"]) for x in pooled_pipe_pq) / n
    cl_lo, cl_hi = _cluster_bootstrap_gap(per_slice_b1, rng)

    res = {
        "metadata": {
            "provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
            "kappa": list(KAPPA), "seed": SEED, "pcts": list(PCTS),
            "bind": list(BIND), "mask": MASK,
            "n_slices": len(slices_out), "skipped": skipped,
        },
        "slices": slices_out,
        "pooled": {
            "n": n,
            "B1_hidden_violation_rate": round(b1_hv, 6),
            "B1_cluster_ci95": [round(cl_lo, 6), round(cl_hi, 6)],
            "pipeline_hidden_violation_rate": round(pipe_hv, 6),
            "pipeline_coverage": round(pipe_cov, 6),
            "pipeline_commit_feasible_minsuff": n_pipe_commit_ok,
            "pipeline_total": n_pipe_total,
            "named_axis_distribution": named_counts,
            "b1_vs_pipeline_significance": sig,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "masked_cost.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    # markdown summary
    lines = ["# E1 — masked-COST validation (bind quality+cost, mask cost)", ""]
    lines.append(f"- slices: {len(slices_out)} (skipped: {len(skipped)})")
    lines.append(f"- pooled n = {n}")
    lines.append("")
    lines.append("| slice | B1 HVR | B1 cov | B2 cov | B3 cov | B6 cov | sel cov |")
    lines.append("|---|---|---|---|---|---|---|")
    for _key, blk in slices_out.items():
        m = blk["meta"]
        lines.append(
            f"| {m['benchmark']} | {m['b1_hidden_violation_rate']:.3f} | "
            f"{m['b1_coverage']:.2f} | {m['b2_coverage']:.2f} | "
            f"{m['b3_coverage']:.2f} | {m['b6_coverage']:.2f} | "
            f"{m['selective_coverage']:.2f} |")
    lines.append("")
    p = res["pooled"]
    lines.append(
        f"**Pooled:** B1 (leaderboard fallback) HVR **{p['B1_hidden_violation_rate']:.4f}** "
        f"(slice-clustered 95% CI [{p['B1_cluster_ci95'][0]:.3f}, "
        f"{p['B1_cluster_ci95'][1]:.3f}]); B2/B3/B6 coverage 0 everywhere "
        f"(objective unobservable -> degenerate); selective abstains and names "
        f"{p['named_axis_distribution']}; pipeline coverage "
        f"{p['pipeline_coverage']:.3f}, HVR {p['pipeline_hidden_violation_rate']:.4f}, "
        f"feasible+min-sufficient {p['pipeline_commit_feasible_minsuff']}/{p['pipeline_total']}; "
        f"B1-vs-pipeline McNemar {sig['mcnemar_b']}/{sig['mcnemar_c']}, "
        f"p={sig['binom_p_one_sided']:.2e}.")
    (OUT_DIR / "masked_cost.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines[-3:]))
    print(f"\nWrote {OUT_DIR/'masked_cost.json'} and .md")


if __name__ == "__main__":
    main()
