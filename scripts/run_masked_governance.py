"""E11 — proxy harm validation on a CATEGORICAL governance-like axis.

Round-8 review, W3/Q2: the harm validation (the 57.1% hidden-violation rate) is
entirely on the CONTINUOUS quality axis, while the decidability headline is driven
by GOVERNANCE. The two halves are bridged only by Proposition 1 (theory), so the
claim "deciding blind on a blind-spot axis ships violations" is never demonstrated
on a governance-LIKE axis. The reviewer asks for "even a proxy validation of harm
on a categorical/governance-like axis." This provides it.

We construct a hard CATEGORICAL admissibility gate over the 11 RouterBench models:
open-weights / self-hostable models are ADMISSIBLE under a data-sovereignty
governance constraint ("the deployment may not send data to a third-party API"),
proprietary-API-only models are INADMISSIBLE. This is a binary 0/1 axis, exactly
the hard-constraint shape governance has (unlike the continuous quality trade-off).

The admissibility truth is supplied here from PUBLIC model metadata (which models
are open-weights), exactly as RouterBench quality is the hidden truth in the
masked-quality battery -- it is a clearly-labelled VALIDATION ground truth, never
injected into the frozen substrate. We:
  1. bind quality >= pctl AND governance(admissibility) >= 1 (self-hostable required),
  2. MASK governance at the read level (it is unmeasured, like real governance),
  3. let each blind rule commit on visible quality+cost,
  4. score against the hidden admissibility truth: a HIDDEN VIOLATION = committing a
     proprietary model under a self-hosting requirement.
Reported alongside the 57.1% continuous-quality result, plus the grading by quality
percentile (how often the cheapest quality-feasible config is also admissible).

Frozen db read-only via the immutable interface; OUR procedure never imputes (it
abstains on the masked governance axis); no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_masked_governance.py
"""

from __future__ import annotations

import json
import random
from collections import namedtuple
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.query import make_query
from prudent_ai.substrate import Substrate
from prudent_ai.validation.baselines import ALL_RULES
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "E11-masked-governance-categorical"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
QUALITY_PCTS = tuple(range(10, 95, 10))  # 10..90 — grade the bite by quality floor
MIN_CFG = 6
MASK = "governance"

# Public model metadata: which of the 11 RouterBench models are open-weights /
# self-hostable (ADMISSIBLE under a data-sovereignty governance constraint).
_RB_MODELS = ValidationRunner._ROUTERBENCH_MODELS
PROPRIETARY = frozenset({
    "rb-claude-instant-v1", "rb-claude-v1", "rb-claude-v2",
    "rb-gpt-3-5-turbo-1106", "rb-gpt-4-1106-preview",
})
# the remaining six (meta-*, mistralai-*, wizardlm-*, zero-one-ai-*) are open-weights
OPEN_WEIGHTS = frozenset(_RB_MODELS) - PROPRIETARY

_Obs = namedtuple("_Obs", ["confidence", "value_num"])


def _model_of(cid: str) -> str | None:
    for m in sorted(_RB_MODELS, key=len, reverse=True):
        if cid.startswith(m + "-"):
            return m
    return None


def _admissible(model: str | None) -> float | None:
    if model is None:
        return None
    return 1.0 if model in OPEN_WEIGHTS else 0.0


class GovernanceTruthSubstrate:
    """C7-shaped wrapper injecting a synthetic binary admissibility (governance) axis.

    cell(x, "governance") returns a single high-confidence 0/1 observation derived
    from public model metadata (open-weights = 1 = self-hostable = admissible). Every
    other axis and method delegates unchanged to the frozen substrate. This is the
    masked-and-scored VALIDATION truth, never written to the substrate.
    """

    def __init__(self, sub) -> None:
        self._sub = sub

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        if a == MASK:
            xid = x if isinstance(x, str) else getattr(x, "id", x)
            adm = _admissible(_model_of(str(xid)))
            return [_Obs("H", adm)] if adm is not None else []
        return self._sub.cell(x, a)

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def _gov_queries(mp: MaskAndPredict, tau: str) -> list:
    """Bind quality >= pctl AND governance(admissibility) >= 1 (self-hostable)."""
    qpct = mp.observed_percentiles(tau, "quality", list(QUALITY_PCTS))
    if not qpct:
        return []
    queries = []
    for p in QUALITY_PCTS:
        cons = [("quality", ">=", qpct[p]), (MASK, ">=", 1.0)]
        q = make_query(tau, cons, label=f"q@p{p}+gov>=1")
        queries.append((p, q))
    return queries


def main() -> None:
    base = CachedSubstrate(Substrate(DB_PATH))
    gov = GovernanceTruthSubstrate(base)
    runner = ValidationRunner(base, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)

    by_name = {r.name: r for r in ALL_RULES}
    blind = ["B2_observed_pareto", "B3_imputation", "B6_cost_accuracy"]
    keys = blind + ["B5_oracle", "selective_strict", "selective_measured"]

    pooled = {k: [] for k in keys}
    by_pct = {p: {"n_commit": 0, "n_violation": 0} for p in QUALITY_PCTS}  # B2 grading
    n_slices = 0
    n_admissible_exists = 0  # slices where >=1 admissible config meets the quality floor
    skipped = []

    for bench in benches:
        bsub = BenchmarkSubstrate(gov, bench)
        if len(bsub.candidates("routerbench")) < MIN_CFG:
            skipped.append(bench)
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        pq = _gov_queries(mp, "routerbench")
        if not pq:
            skipped.append(bench)
            continue
        n_slices += 1

        for p, q in pq:
            # does a truly-admissible, quality-feasible config exist? (bind-and-bite check)
            oracle_cfg = by_name["B5_oracle"].decide(bsub, q, None, KAPPA, PHI)
            if oracle_cfg is not None:
                n_admissible_exists += 1

            for k in blind:
                rule = by_name[k]
                out = mp.score_rule_per_query(rule, [q], MASK)[0]
                pooled[k].append(out)
                if k == "B2_observed_pareto" and out["committed"]:
                    by_pct[p]["n_commit"] += 1
                    if out["hidden_violation"]:
                        by_pct[p]["n_violation"] += 1

            # oracle (sees governance): commits cheapest admissible -> 0 violations
            ores = mp.score_rule_per_query(by_name["B5_oracle"], [q], MASK)[0]
            pooled["B5_oracle"].append(ores)
            # selective strict: governance binds + masked -> abstains
            sres = mp.score_rule_per_query(by_name["selective"], [q], MASK)[0]
            pooled["selective_strict"].append(sres)
            # selective + named measurement: abstain, measure governance, commit
            # the cheapest admissible config == the oracle commitment -> 0 violations
            pooled["selective_measured"].append(
                {"committed": ores["committed"], "hidden_violation": ores["hidden_violation"]})

    def summarize(key):
        v = pooled[key]
        nc = sum(int(x["committed"]) for x in v)
        nv = sum(int(x["hidden_violation"]) for x in v)
        return {"n": len(v), "n_committed": nc, "n_violations": nv,
                "coverage": round(nc / len(v), 4) if v else 0.0,
                "hvr": round(nv / nc, 4) if nc else 0.0}

    summary = {k: summarize(k) for k in keys}
    paired = ValidationRunner._paired_significance(
        pooled["B2_observed_pareto"], pooled["selective_measured"], rng)

    grading = {}
    for p in QUALITY_PCTS:
        c = by_pct[p]
        grading[p] = {"n_commit": c["n_commit"], "n_violation": c["n_violation"],
                      "hvr": round(c["n_violation"] / c["n_commit"], 4)
                      if c["n_commit"] else 0.0}

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
                     "kappa": list(KAPPA), "seed": SEED, "mask": MASK,
                     "quality_pcts": list(QUALITY_PCTS), "n_slices": n_slices,
                     "n_query_instances": len(pooled["B2_observed_pareto"]),
                     "admissible_exists_instances": n_admissible_exists,
                     "proprietary_models": sorted(PROPRIETARY),
                     "open_weights_models": sorted(OPEN_WEIGHTS),
                     "note": "categorical admissibility (1=open-weights/self-hostable, "
                             "0=proprietary-API) is a clearly-labelled validation truth "
                             "from public metadata, NOT a substrate row. Compare HVR to "
                             "the 57.1% on the continuous quality axis."},
        "pooled": summary,
        "b2_hvr_by_quality_percentile": grading,
        "paired_B2_vs_selective_measured": paired,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "masked_governance.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    b2 = summary["B2_observed_pareto"]
    lines = [
        "# E11 — proxy harm on a CATEGORICAL governance-like axis (self-hostable gate)",
        "",
        f"- {n_slices} benchmark slices, {len(pooled['B2_observed_pareto'])} query "
        f"instances (quality floor x self-hosting gate)",
        f"- admissible (open-weights) configs: {sorted(OPEN_WEIGHTS)}",
        f"- inadmissible (proprietary): {sorted(PROPRIETARY)}",
        "",
        "| rule | coverage | HVR (categorical) | committed | violations |",
        "|---|---|---|---|---|",
    ]
    for k in keys:
        s = summary[k]
        lines.append(f"| {k} | {s['coverage']:.2f} | {s['hvr']:.4f} | "
                     f"{s['n_committed']} | {s['n_violations']} |")
    lines += [
        "",
        f"- **blind commitment (B2) hidden-violation rate on the categorical gate: "
        f"**{100 * b2['hvr']:.1f}%** "
        f"(vs 57.1% on the continuous quality axis)",
        f"- admissible config exists on {n_admissible_exists}/"
        f"{len(pooled['B2_observed_pareto'])} instances (oracle/selective reach 0 "
        f"violations -> baselines fail for lack of evidence, not options)",
        f"- B2 vs selective+measurement: McNemar "
        f"{paired['mcnemar_b']}/{paired['mcnemar_c']}, p={paired['binom_p_one_sided']:.2e}",
        "",
        "## grading: B2 hidden-violation rate by quality floor (percentile)",
        "",
        "| quality pct | commit | violations | HVR |",
        "|---|---|---|---|",
    ]
    for p in QUALITY_PCTS:
        g = grading[p]
        lines.append(f"| p{p} | {g['n_commit']} | {g['n_violation']} | "
                     f"{100 * g['hvr']:.1f}% |")
    (OUT_DIR / "masked_governance.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'masked_governance.json'} and .md")


if __name__ == "__main__":
    main()
