"""E7 — Bayesian expected-regret baseline B7 in the masked-quality battery.

Round-4 review, W7/Q4: the never-impute argument so far defeats POINT imputation
(median fill B3, learned per-model mean B3'). A skeptical practitioner would reach
for a genuinely probabilistic rule: place a PRIOR over the masked axis and minimize
EXPECTED feasibility-weighted regret, not a point estimate. This adds that rule.

B7 (Bayesian expected-regret):
  per model m, posterior over the masked quality axis = N(mu_m, sigma_m) fit from
  the SAME leave-one-benchmark-out cross-benchmark quality samples B3' uses
  (sigma from the sample spread; a global pooled posterior backs off models with
  no cross-benchmark samples). Among candidates satisfying the VISIBLE constraints,
  commit the one minimizing
      E_theta[ loss ] = visible_cost(x)  +  lambda * P(quality(x) < threshold)
  where P(.) is the closed-form Normal CDF (math.erf, no scipy). This is a proper
  Bayes rule against the masked constraint, reported at two lambda.

Comparison: B2 (=B3 median, coincide), B3' (learned point), B7 (Bayes), scored
against the hidden truth. Frozen db read-only via the immutable interface; the
per-slice mask keeps cross-benchmark cells visible (SliceMaskedSubstrate); no
mutation; OUR procedure still never imputes (B7 is a stressed BASELINE).

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_bayesian_baseline.py
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
PROVENANCE = "E7-bayesian-baseline"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6
MASK = "quality"
LAMBDAS = (1.0, 4.0)
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
    learned/Bayesian imputer would exploit.
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


class B3PrimeLearnedImputer(DecisionRule):
    """Leave-one-benchmark-out per-model mean (the learned POINT competitor)."""

    name = "B3prime_learned_imputer"

    def __init__(self, benchmark: str, benches: list[str]) -> None:
        self._others = [b for b in benches if b != benchmark]

    def _imputed_quality(self, sub, model: str) -> float | None:
        vals = _model_samples(sub, model, self._others)
        return sum(vals) / len(vals) if vals else None

    def decide(self, sub, query, visible_regime, kappa, phi):
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            model = _model_of(c.id)
            ok = True
            for con in query.bundle:
                if con.axis == MASK:
                    val = self._imputed_quality(sub, model) if model else None
                else:
                    bel = aggregate(sub.cell(c.id, con.axis), kappa, phi)
                    val = bel.point if bel.is_present else None
                if val is None:
                    continue
                if not _satisfies(con.op, val, float(con.value)):
                    ok = False
                    break
            if not ok:
                continue
            cb = aggregate(sub.cell(c.id, "cost"), kappa, phi)
            if not cb.is_present:
                continue
            if best_cost is None or cb.point < best_cost:
                best, best_cost = c.id, cb.point
        return best


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


class B7BayesianExpectedRegret(DecisionRule):
    """Posterior over masked quality; minimize expected feasibility-weighted regret."""

    name = "B7_bayesian_expected_regret"

    def __init__(self, benchmark: str, benches: list[str], lam: float,
                 global_mu: float, global_sigma: float) -> None:
        self._others = [b for b in benches if b != benchmark]
        self._lam = lam
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
        """P(masked axis violates the constraint) under N(mu, sigma)."""
        t = float(con.value)
        sigma = max(sigma, SIGMA_FLOOR)
        # quality constraint is op '>=': violate iff quality < t
        below = _norm_cdf((t - mu) / sigma)
        return below if con.op == ">=" else 1.0 - below

    def decide(self, sub, query, visible_regime, kappa, phi):
        best, best_loss = None, None
        for c in sub.candidates(query.tau):
            ok = True
            p_violate = 0.0
            for con in query.bundle:
                if con.axis == MASK:
                    mu, sigma = self._posterior(sub, _model_of(c.id))
                    p_violate = self._p_violate(mu, sigma, con)
                    continue
                bel = aggregate(sub.cell(c.id, con.axis), kappa, phi)
                if not bel.is_present:
                    continue  # like B2/B3: unknowable visible constraint skipped
                if not _satisfies(con.op, bel.point, float(con.value)):
                    ok = False
                    break
            if not ok:
                continue
            cb = aggregate(sub.cell(c.id, "cost"), kappa, phi)
            if not cb.is_present:
                continue
            loss = cb.point + self._lam * p_violate
            if best_loss is None or loss < best_loss:
                best, best_loss = c.id, loss
        return best


def _global_posterior(sub, benches: list[str]) -> tuple[float, float]:
    vals: list[float] = []
    for m in _RB_MODELS:
        vals.extend(_model_samples(sub, m, benches))
    if not vals:
        return 0.5, 0.1
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / max(1, len(vals) - 1)
    return mu, max(math.sqrt(var), SIGMA_FLOOR)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)
    g_mu, g_sigma = _global_posterior(sub, benches)

    by_name = {r.name: r for r in ALL_RULES}
    b2 = by_name["B2_observed_pareto"]

    keys = ["B2", "B3prime"] + [f"B7_lam{lam:g}" for lam in LAMBDAS]
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
        b3p = B3PrimeLearnedImputer(bench, benches)
        rules = {"B2": b2, "B3prime": b3p}
        for lam in LAMBDAS:
            rules[f"B7_lam{lam:g}"] = B7BayesianExpectedRegret(
                bench, benches, lam, g_mu, g_sigma)

        for k, rule in rules.items():
            for q in queries:
                pred = rule.decide(slice_mask, q, ALL_AXES - {MASK}, KAPPA, PHI)
                committed = pred is not None
                violated = committed and not mp.true_feasible(q, pred)
                # min-sufficiency + cost overshoot among truly-feasible commitments
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

    def hvr(key):
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

    summary = {k: hvr(k) for k in keys}
    paired = {
        f"{k}_vs_B2": ValidationRunner._paired_significance(
            pooled["B2"], pooled[k], rng)
        for k in keys if k != "B2"
    }

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "seed": SEED,
                     "mask": MASK, "lambdas": list(LAMBDAS),
                     "global_posterior": {"mu": round(g_mu, 4),
                                          "sigma": round(g_sigma, 4)},
                     "skipped": skipped},
        "pooled": summary,
        "paired_vs_B2": paired,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "bayesian_baseline.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E7 — Bayesian expected-regret baseline B7 (masked quality)", "",
             f"- global backoff posterior N({g_mu:.3f}, {g_sigma:.3f}); "
             f"lambda in {list(LAMBDAS)}", "",
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
    for k, sig in paired.items():
        lines.append(f"- {k}: mean_diff {sig['mean_diff']:.4f}, "
                     f"McNemar {sig['mcnemar_b']}/{sig['mcnemar_c']}, "
                     f"p={sig['binom_p_one_sided']:.2e}")
    (OUT_DIR / "bayesian_baseline.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'bayesian_baseline.json'} and .md")


if __name__ == "__main__":
    main()
