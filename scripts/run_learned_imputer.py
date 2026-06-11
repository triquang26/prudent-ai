"""F1 — LEARNED imputer baseline B3' in the masked-quality battery (node b5uiav).

Round-2 review, W4/Q2: pool-median imputation is a constant fill; in the masked
RouterBench setting a real training signal exists --- a model's quality on the
masked benchmark is predictable from the SAME model's quality on the OTHER
benchmarks. Test the strongest such imputer honestly.

Design change vs. the published battery: the published MaskedSubstrate hides the
quality axis for EVERY config (corpus-wide missingness). A cross-benchmark
imputer needs the realistic per-slice reading --- "this model has no quality
number on MY task, but it has public numbers elsewhere" --- so here the mask
hides quality ONLY for configs of the benchmark under evaluation
(SliceMaskedSubstrate). B2/B3 behave identically under either mask (they only
read slice candidates); B3' is the only rule that exploits the visible
cross-benchmark cells. Scoring is unchanged (true_feasible against the unmasked
truth). Published code untouched; everything here is script-local.

B3' (leave-one-benchmark-out per-model mean):
  imputed_quality(model m) = mean over benchmarks b' != b of quality(rb-m-b')
  then decide exactly like B2/B3: min visible-cost among candidates whose
  (imputed-quality, visible-cost) satisfy the bundle.

Outputs: outputs/p5/learned_imputer.{json,md}

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_learned_imputer.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.beliefs import aggregate
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.substrate import Substrate
from prudent_ai.validation.baselines import ALL_RULES, DecisionRule, _satisfies
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "F1-learned-imputer"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
PCTS = tuple(range(10, 95, 5))
MIN_CFG = 6
MASK = "quality"

_RB_MODELS = ValidationRunner._ROUTERBENCH_MODELS


def _model_of(cid: str) -> str | None:
    for m in sorted(_RB_MODELS, key=len, reverse=True):
        if cid.startswith(m + "-"):
            return m
    return None


class SliceMaskedSubstrate:
    """Hide *masked_axis* ONLY for configs of one benchmark (suffix match).

    The realistic per-slice missingness: the model is unmeasured on THIS task
    but its public numbers elsewhere stay visible. C7-shaped proxy.
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
    """Leave-one-benchmark-out per-model mean for the masked quality axis."""

    name = "B3prime_learned_imputer"

    def __init__(self, root_sub, benchmark: str, benches: list[str]) -> None:
        # root_sub: the UNwrapped substrate (full candidate set) used only to
        # enumerate sibling configs; reads still go through the slice mask the
        # harness hands to decide() (cross-benchmark quality is visible there).
        self._root = root_sub
        self._bench = benchmark
        self._others = [b for b in benches if b != benchmark]

    def _imputed_quality(self, sub, model: str) -> float | None:
        vals = []
        for b in self._others:
            cid = f"{model}-{b}"
            cells = sub.cell(cid, "quality")
            if not cells:
                continue
            bel = aggregate(cells, KAPPA, PHI)
            if bel.is_present:
                vals.append(bel.point)
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
                    continue  # like B2/B3: an unknowable constraint is skipped
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


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)

    by_name = {r.name: r for r in ALL_RULES}
    b2, b3, sel = (by_name["B2_observed_pareto"], by_name["B3_imputation"],
                   by_name["selective"])

    slices_out = {}
    pooled = {k: [] for k in ("B2", "B3", "B3prime", "selective")}
    per_slice_counts = []  # (n, viol_b2, viol_b3p) for clustered CI
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
        b3p = B3PrimeLearnedImputer(sub, bench, benches)
        slice_mask = SliceMaskedSubstrate(bsub, MASK, bench)

        def score(rule, *, _bsub=bsub, _mask=slice_mask, _qs=queries, _mp=mp,
                  sees_all=False):
            from prudent_ai.solver.regimes import ALL_AXES
            rsub = _bsub if sees_all else _mask
            visible = ALL_AXES - {MASK}
            out = []
            for q in _qs:
                pred = rule.decide(rsub, q, visible, KAPPA, PHI)
                committed = pred is not None
                violated = committed and not _mp.true_feasible(q, pred)
                out.append({"committed": committed, "hidden_violation": violated})
            return out

        pq = {
            "B2": score(b2),
            "B3": score(b3),
            "B3prime": score(b3p),
            "selective": score(sel),
        }
        for k in pooled:
            pooled[k].extend(pq[k])
        n = len(queries)
        viol = {k: sum(int(x["hidden_violation"]) for x in v)
                for k, v in pq.items()}
        cov = {k: sum(int(x["committed"]) for x in v) / n for k, v in pq.items()}
        per_slice_counts.append((n, viol["B2"], viol["B3prime"]))
        slices_out[bench] = {
            "n_queries": n,
            "hvr": {k: round(viol[k] / max(1, sum(int(x['committed']) for x in pq[k])), 4)
                    for k in pq},
            "coverage": {k: round(cov[k], 4) for k in pq},
            "n_violations": viol,
        }

    def pooled_hvr(key):
        v = pooled[key]
        ncommit = sum(int(x["committed"]) for x in v)
        nviol = sum(int(x["hidden_violation"]) for x in v)
        return nviol, ncommit, (nviol / ncommit if ncommit else 0.0)

    res_pooled = {}
    for k in pooled:
        nv, nc, r = pooled_hvr(k)
        res_pooled[k] = {"n_committed": nc, "n_violations": nv,
                         "hvr": round(r, 4)}

    # clustered CI for B3prime HVR
    K = len(per_slice_counts)
    boots = []
    for _ in range(10000):
        samp = [per_slice_counts[rng.randrange(K)] for _ in range(K)]
        nq = sum(s[0] for s in samp)
        nv = sum(s[2] for s in samp)
        boots.append(nv / nq if nq else 0.0)
    boots.sort()
    b3p_ci = [round(boots[250], 4), round(boots[9749], 4)]

    # paired B3 vs B3prime (does learning beat the constant fill?)
    sig = ValidationRunner._paired_significance(pooled["B3"], pooled["B3prime"], rng)

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "seed": SEED,
                     "mask": MASK, "n_slices": len(slices_out),
                     "skipped": skipped,
                     "imputer": "leave-one-benchmark-out per-model mean"},
        "slices": slices_out,
        "pooled": res_pooled,
        "B3prime_cluster_ci95": b3p_ci,
        "B3_vs_B3prime_paired": sig,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "learned_imputer.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# F1 — learned imputer B3' (leave-one-benchmark-out per-model mean)",
             ""]
    lines.append(f"- slices: {len(slices_out)}; mask=quality (per-slice mask: "
                 "cross-benchmark quality stays visible to B3' only)")
    lines.append("")
    lines.append("| rule | pooled HVR | committed | violations |")
    lines.append("|---|---|---|---|")
    for k, v in res_pooled.items():
        lines.append(f"| {k} | {v['hvr']:.4f} | {v['n_committed']} | "
                     f"{v['n_violations']} |")
    lines.append("")
    lines.append(f"- B3' clustered 95% CI on HVR: {b3p_ci}")
    lines.append(f"- B3 (median) vs B3' (learned) paired: diff "
                 f"{sig['mean_diff']:.4f}, McNemar {sig['mcnemar_b']}/"
                 f"{sig['mcnemar_c']}, p={sig['binom_p_one_sided']:.2e}")
    (OUT_DIR / "learned_imputer.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR/'learned_imputer.json'} and .md")


if __name__ == "__main__":
    main()
