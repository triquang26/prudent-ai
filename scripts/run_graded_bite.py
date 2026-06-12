"""Q3 — graded bite: violation rate vs how strongly cheap configs trade off the axis.

Round-5 review, Q3: "Can you characterize how the 57.1% harm number behaves as the
hidden axis's cheap-trades-it-off property weakens, beyond the binary no-bite
control?" The binary control says: a slice does not bite when cheap configs happen
to satisfy the hidden axis. We make that continuous.

Per RouterBench slice we compute a TRADE-OFF STRENGTH = Spearman rank correlation
between a config's true cost and its true quality (the hidden axis) across the 11
models. Positive ==> cheaper models are lower-quality ==> committing the cheapest
config tends to violate a quality floor (strong bite); near-zero / negative ==>
cheap configs are already high quality ==> the no-bite regime. Against this we plot
the per-slice blind-commit (B2 observed-Pareto) hidden-violation rate. We also give
the complementary view from the existing per-query percentile sweep: violation rate
vs the quality-constraint percentile (tighter constraint ==> cheap configs
increasingly fail it).

Frozen db read-only via the immutable interface; no mutation; nothing imputed.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_graded_bite.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.substrate import Substrate
from prudent_ai.validation.baselines import ALL_RULES
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "Q3-graded-bite"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6
MASK = "quality"


def _ranks(xs: list[float]) -> list[float]:
    """Average ranks (1-based), ties averaged."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    b2 = next(r for r in ALL_RULES if r.name == "B2_observed_pareto")

    per_slice = []
    pct_commit = dict.fromkeys(PCTS, 0)
    pct_viol = dict.fromkeys(PCTS, 0)
    for bench in benches:
        bsub = BenchmarkSubstrate(sub, bench)
        cfgs = bsub.candidates("routerbench")
        if len(cfgs) < MIN_CFG:
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        # true cost/quality across the configs -> trade-off strength
        cost, qual = [], []
        for c in cfgs:
            cv = mp._true_val(c.id, "cost")
            qv = mp._true_val(c.id, "quality")
            if cv is not None and qv is not None:
                cost.append(cv)
                qual.append(qv)
        if len(cost) < MIN_CFG:
            continue
        tradeoff = _spearman(cost, qual)  # +ve: cheap == lower quality == strong bite
        queries = mp.generate_queries("routerbench", ("quality",), pcts=PCTS)
        if not queries:
            continue
        pq = mp.score_rule_per_query(b2, queries, MASK)
        ncommit = sum(int(x["committed"]) for x in pq)
        nviol = sum(int(x["hidden_violation"]) for x in pq)
        hvr = nviol / ncommit if ncommit else 0.0
        per_slice.append({"benchmark": bench, "tradeoff_strength": round(tradeoff, 4),
                          "hvr": round(hvr, 4), "n_committed": ncommit,
                          "n_violations": nviol})
        for p, rec in zip(PCTS, pq, strict=True):
            if rec["committed"]:
                pct_commit[p] += 1
                pct_viol[p] += int(rec["hidden_violation"])

    # across-slice relationship
    ts = [s["tradeoff_strength"] for s in per_slice]
    hv = [s["hvr"] for s in per_slice]
    corr = _spearman(ts, hv)
    # tercile bins by trade-off strength
    order = sorted(per_slice, key=lambda s: s["tradeoff_strength"])
    k = len(order)
    bins = {"weak": order[: k // 3], "mid": order[k // 3: 2 * k // 3],
            "strong": order[2 * k // 3:]}
    bin_summary = {}
    for name, grp in bins.items():
        if not grp:
            continue
        tot_c = sum(s["n_committed"] for s in grp)
        tot_v = sum(s["n_violations"] for s in grp)
        bin_summary[name] = {
            "n_slices": len(grp),
            "tradeoff_range": [grp[0]["tradeoff_strength"], grp[-1]["tradeoff_strength"]],
            "mean_hvr": round(tot_v / tot_c, 4) if tot_c else 0.0,
        }
    # percentile-graded view
    pct_curve = {str(p): {"coverage_weighted_violation_rate":
                          round(pct_viol[p] / pct_commit[p], 4) if pct_commit[p] else 0.0,
                          "n_committed": pct_commit[p]} for p in PCTS}

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
                     "kappa": list(KAPPA), "mask": MASK, "n_slices": len(per_slice),
                     "tradeoff": "spearman(cost, quality) across configs; +ve = cheap "
                                 "is lower-quality = strong trade-off"},
        "across_slice_spearman_tradeoff_vs_hvr": round(corr, 4),
        "bins_by_tradeoff": bin_summary,
        "per_slice": sorted(per_slice, key=lambda s: s["tradeoff_strength"]),
        "violation_rate_by_constraint_percentile": pct_curve,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "graded_bite.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# Q3 — graded bite: violation rate vs trade-off strength", "",
             f"- across-slice Spearman(trade-off strength, B2 violation rate) = "
             f"**{corr:.3f}** over {len(per_slice)} slices", "",
             "| trade-off tercile | slices | trade-off range | mean violation rate |",
             "|---|---|---|---|"]
    for name in ("weak", "mid", "strong"):
        if name in bin_summary:
            b = bin_summary[name]
            lines.append(f"| {name} | {b['n_slices']} | "
                         f"[{b['tradeoff_range'][0]:.2f}, {b['tradeoff_range'][1]:.2f}] | "
                         f"{100 * b['mean_hvr']:.1f}% |")
    lines += ["", "## Violation rate by quality-constraint percentile (graded view)", "",
              "| percentile | violation rate | committed |", "|---|---|---|"]
    for p in PCTS:
        c = pct_curve[str(p)]
        lines.append(f"| p{p} | {100 * c['coverage_weighted_violation_rate']:.1f}% | "
                     f"{c['n_committed']} |")
    (OUT_DIR / "graded_bite.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'graded_bite.json'} and .md")


if __name__ == "__main__":
    main()
