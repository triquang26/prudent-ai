"""B8 — chance-constrained Bayesian baseline in the masked-quality battery.

Round-7 review, Q2: the round-4 Bayesian rule B7 minimizes EXPECTED feasibility-
weighted regret (cost + lambda * P(violate)) and drives violations to 4.7% only by
over-provisioning ~70x. The reviewer asks: is the 70x overshoot driven by the
EXPECTED-REGRET OBJECTIVE, or by the WIDE POSTERIOR over the masked axis? A natural
alternative is a CHANCE CONSTRAINT: among candidates satisfying the visible
constraints AND with P(violate) <= alpha under the same posterior, commit the
CHEAPEST. If the wall is the objective, the chance constraint should recover
minimum-sufficiency at some alpha; if the wall is the posterior (partial
identification), no alpha gives both low HVR and nonzero min-sufficiency.

B8 (chance-constrained):
  same per-model Normal posterior over the masked quality axis as B7 (leave-one-
  benchmark-out cross-benchmark samples; global pooled backoff). Among candidates
  satisfying the VISIBLE constraints and with P(quality < threshold) <= alpha,
  commit the one of minimum VISIBLE cost; abstain if none qualifies. Swept over
  alpha in {0.01, 0.05, 0.10, 0.20}.

This mirrors run_bayesian_baseline.py (B7) exactly except the decision rule, so the
posterior, mask, slices, kappa, phi, and metrics are identical and comparable.
Frozen db read-only via the immutable interface; the per-slice mask keeps cross-
benchmark cells visible (SliceMaskedSubstrate); no mutation; OUR procedure still
never imputes (B8 is a stressed BASELINE, like B7).

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_chance_constrained.py
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.beliefs import aggregate
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.substrate import Substrate
from prudent_ai.validation.baselines import ALL_RULES, DecisionRule, _satisfies
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "B8-chance-constrained"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6
MASK = "quality"
ALPHAS = (0.01, 0.05, 0.10, 0.20)
SIGMA_FLOOR = 0.02  # avoid degenerate 0/1 violation probabilities

_RB_MODELS = ValidationRunner._ROUTERBENCH_MODELS


def _model_of(cid: str) -> str | None:
    for m in sorted(_RB_MODELS, key=len, reverse=True):
        if cid.startswith(m + "-"):
            return m
    return None


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class SliceMaskedSubstrate:
    """Hide *masked_axis* ONLY for configs of one benchmark (suffix match).

    Cross-benchmark cells stay visible — the realistic per-slice missingness a
    learned/Bayesian imputer would exploit. Identical to run_bayesian_baseline.py.
    """

    def __init__(self, sub, masked_axis: str, benchmark: str) -> None:
        self._sub = sub
        self._masked = masked_axis
        self._suffix = f"-{benchmark}"

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        xid = x if isinstance(x, str) else getattr(x, "id", x)
        if a == self._masked and str(xid).endswith(self._suffix):
            return []
        return self._sub.cell(x, a)

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def _model_samples(sub, model: str, others: list[str]) -> list[float]:
    vals = []
    for b in others:
        cells = sub.cell(f"{model}-{b}", "quality")
        if not cells:
            continue
        bel = aggregate(cells, KAPPA, PHI)
        if bel.is_present:
            vals.append(bel.point)
    return vals


def _global_posterior(sub, benches: list[str]) -> tuple[float, float]:
    vals: list[float] = []
    for m in _RB_MODELS:
        vals.extend(_model_samples(sub, m, benches))
    if not vals:
        return 0.5, 0.1
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / max(1, len(vals) - 1)
    return mu, max(math.sqrt(var), SIGMA_FLOOR)


class B8ChanceConstrained(DecisionRule):
    """Posterior over masked quality; commit cheapest config with P(violate) <= alpha."""

    name = "B8_chance_constrained"

    def __init__(self, benchmark: str, benches: list[str], alpha: float,
                 global_mu: float, global_sigma: float) -> None:
        self._others = [b for b in benches if b != benchmark]
        self._alpha = alpha
        self._g_mu = global_mu
        self._g_sigma = global_sigma

    def _posterior(self, sub, model: str | None) -> tuple[float, float]:
        vals = _model_samples(sub, model, self._others) if model else []
        if not vals:
            return self._g_mu, self._g_sigma
        mu = sum(vals) / len(vals)
        if len(vals) > 1:
            var = sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)
            sigma = max(math.sqrt(var), SIGMA_FLOOR)
        else:
            sigma = self._g_sigma
        return mu, sigma

    def _p_violate(self, mu: float, sigma: float, con) -> float:
        t = float(con.value)
        sigma = max(sigma, SIGMA_FLOOR)
        below = _norm_cdf((t - mu) / sigma)  # P(quality < t)
        return below if con.op == ">=" else 1.0 - below

    def decide(self, sub, query, visible_regime, kappa, phi):
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            ok = True
            for con in query.bundle:
                if con.axis == MASK:
                    mu, sigma = self._posterior(sub, _model_of(c.id))
                    if self._p_violate(mu, sigma, con) > self._alpha:
                        ok = False  # chance constraint violated -> drop candidate
                        break
                    continue
                bel = aggregate(sub.cell(c.id, con.axis), kappa, phi)
                if not bel.is_present:
                    continue  # like B2/B7: unknowable visible constraint skipped
                if not _satisfies(con.op, bel.point, float(con.value)):
                    ok = False
                    break
            if not ok:
                continue
            cb = aggregate(sub.cell(c.id, "cost"), kappa, phi)
            if not cb.is_present:
                continue
            if best_cost is None or cb.point < best_cost:  # cheapest qualifying
                best, best_cost = c.id, cb.point
        return best


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)
    g_mu, g_sigma = _global_posterior(sub, benches)

    by_name = {r.name: r for r in ALL_RULES}
    b2 = by_name["B2_observed_pareto"]

    keys = ["B2"] + [f"B8_a{a:g}" for a in ALPHAS]
    pooled = {k: [] for k in keys}
    skipped = []
    for bench in benches:
        bsub = BenchmarkSubstrate(sub, bench)
        if len(bsub.candidates("routerbench")) < MIN_CFG:
            skipped.append(bench)
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        queries = mp.generate_queries("routerbench", ("quality",), pcts=PCTS)
        if not queries:
            skipped.append(bench)
            continue
        slice_mask = SliceMaskedSubstrate(bsub, MASK, bench)
        rules = {"B2": b2}
        for a in ALPHAS:
            rules[f"B8_a{a:g}"] = B8ChanceConstrained(
                bench, benches, a, g_mu, g_sigma)

        for k, rule in rules.items():
            for q in queries:
                pred = rule.decide(slice_mask, q, ALL_AXES - {MASK}, KAPPA, PHI)
                committed = pred is not None
                violated = committed and not mp.true_feasible(q, pred)
                minsuff = False
                overshoot = None
                if committed and not violated:
                    oc = mp.oracle_cost(q)
                    pc = mp._true_val(pred, "cost")
                    if oc is not None and pc is not None:
                        minsuff = abs(pc - oc) < 1e-9
                        overshoot = (pc - oc) / oc if oc > 0 else 0.0
                pooled[k].append({"committed": committed,
                                  "hidden_violation": violated,
                                  "min_sufficient": minsuff,
                                  "overshoot": overshoot})

    def summarize(key):
        v = pooled[key]
        nc = sum(int(x["committed"]) for x in v)
        nv = sum(int(x["hidden_violation"]) for x in v)
        feas = [x for x in v if x["committed"] and not x["hidden_violation"]]
        n_minsuff = sum(int(x["min_sufficient"]) for x in feas)
        oss = [x["overshoot"] for x in feas if x["overshoot"] is not None]
        return {"n": len(v), "n_committed": nc, "n_violations": nv,
                "coverage": round(nc / len(v), 4) if v else 0.0,
                "hvr": round(nv / nc, 4) if nc else 0.0,
                "n_feasible": len(feas),
                "min_sufficient_rate": round(n_minsuff / len(feas), 4) if feas else 0.0,
                "mean_cost_overshoot": round(sum(oss) / len(oss), 4) if oss else 0.0}

    summary = {k: summarize(k) for k in keys}
    paired = {
        f"{k}_vs_B2": ValidationRunner._paired_significance(
            pooled["B2"], pooled[k], rng)
        for k in keys if k != "B2"
    }

    # Verdict: does ANY alpha achieve both low HVR (<= 0.10) AND nonzero min-suff?
    both = [k for k in keys if k != "B2"
            and summary[k]["hvr"] <= 0.10
            and summary[k]["min_sufficient_rate"] > 0.0]

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "seed": SEED,
                     "mask": MASK, "alphas": list(ALPHAS),
                     "global_posterior": {"mu": round(g_mu, 4),
                                          "sigma": round(g_sigma, 4)},
                     "skipped": skipped},
        "pooled": summary,
        "paired_vs_B2": paired,
        "any_alpha_low_hvr_and_minsuff": both,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "chance_constrained.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# B8 — chance-constrained Bayesian (masked quality)", "",
             f"- global backoff posterior N({g_mu:.3f}, {g_sigma:.3f}); "
             f"alpha in {list(ALPHAS)}",
             "- rule: commit cheapest config with P(quality<threshold) <= alpha; "
             "abstain if none", "",
             "| rule | coverage | HVR | min-suff rate | mean cost overshoot | "
             "committed | violations |",
             "|---|---|---|---|---|---|---|"]
    for k in keys:
        s = summary[k]
        lines.append(f"| {k} | {s['coverage']:.2f} | {s['hvr']:.4f} | "
                     f"{s['min_sufficient_rate']:.4f} | "
                     f"{s['mean_cost_overshoot']:.3f} | "
                     f"{s['n_committed']} | {s['n_violations']} |")
    lines.append("")
    lines.append(f"- alpha(s) achieving BOTH HVR<=0.10 and min-suff>0: "
                 f"{both if both else 'NONE'}")
    lines.append("")
    for k, sig in paired.items():
        lines.append(f"- {k}: mean_diff {sig['mean_diff']:.4f}, "
                     f"McNemar {sig['mcnemar_b']}/{sig['mcnemar_c']}, "
                     f"p={sig['binom_p_one_sided']:.2e}")
    (OUT_DIR / "chance_constrained.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'chance_constrained.json'} and .md")


if __name__ == "__main__":
    main()
