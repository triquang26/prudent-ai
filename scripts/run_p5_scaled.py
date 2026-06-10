"""Run the SCALED P5 V1 validation battery (significance + multiple biting slices).

Scales P5 V1 from the n=5 pilot to a real battery: a larger per-slice query
battery (pcts 10..90 step 5) over BFCL plus six per-benchmark RouterBench slices
(``BenchmarkSubstrate`` holds the benchmark fixed so the 11 models are
cost-comparable → the cost-minimizer is the weakest model → masking the quality
floor bites). For each slice we run the full baseline lattice (B1–B6 + selective),
collect per-rule coverage + hidden_violation_rate + counts, and run a paired
significance test (McNemar-style discordant count + seeded bootstrap 95% CI on the
hidden-violation-rate DIFFERENCE) of selective vs the must-beat baselines B2
(observed-Pareto) and B3 (imputation). Results are pooled across the biting slices.

Writes:
  - outputs/p5/validation_scaled.json  — full results + provenance (no wall-clock).
  - outputs/p5/validation_scaled.md    — per-slice baseline-lattice tables + the
                                         significance block (pooled HV B2/B3 vs
                                         selective, difference, 95% CI, n, sig).

Every verdict reads the substrate ONLY through the solver/validation layer (C7).
The substrate is wrapped in CachedSubstrate so the battery does not re-hit SQLite.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p5_scaled.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p5")
PROVENANCE = "P5-scaled"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345

_RULE_ORDER = [
    "B1_accuracy_only",
    "B2_observed_pareto",
    "B3_imputation",
    "B4_missing_as_fail",
    "B5_oracle",
    "B6_cost_accuracy",
    "selective",
]


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def _render_md(res: dict) -> str:
    meta = res["meta"]
    lines: list[str] = []
    lines.append("# P5 Validation (SCALED) — V1 battery with significance")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ (aggregation): `{PHI.value}`")
    lines.append(f"- κ (confidence policy): `{'+'.join(KAPPA)}`")
    lines.append(f"- seed: `{meta['seed']}`  (bootstrap + any draws)")
    lines.append(
        f"- pcts: `{meta['pcts'][0]}..{meta['pcts'][-1]} step 5` "
        f"({len(meta['pcts'])} queries / slice)"
    )
    lines.append(
        f"- slices: {meta['n_slices']} total, {meta['n_biting_slices']} biting "
        f"({meta['n_biting_slices_h']} H-confidence); "
        f"total queries {meta['total_queries']} ({meta['biting_queries']} on biting "
        f"slices, {meta['biting_queries_h']} on H-confidence biting slices)"
    )
    if meta.get("skipped_slices"):
        lines.append(
            f"- skipped (degenerate, too few cost-comparable configs): "
            f"{', '.join(meta['skipped_slices'])}"
        )
    lines.append("")

    # ---- per-slice lattice ----
    lines.append("## Per-slice baseline lattice")
    lines.append("")
    lines.append(
        "Per slice: each rule predicts a committed config (or abstains) under the "
        "masked regime, scored against the true (full-regime) values. "
        "`hidden_violation_rate` = fraction of COMMITs that silently violate the "
        "masked truth."
    )
    lines.append("")
    for key, block in res["slices"].items():
        m = block["meta"]
        rules = block["rules"]
        tag = "BITING" if m["baselines_bite"] else "no-bite"
        lines.append(f"### {key}  ({tag})")
        lines.append("")
        lines.append(
            f"τ=`{m['tau']}`, benchmark=`{m['benchmark']}`, "
            f"bind=`{'+'.join(m['bind_axes'])}`, mask=`{m['masked_axis']}`, "
            f"n_queries={m['n_queries']}, n_candidates={m['n_candidates']}"
        )
        lines.append("")
        lines.append(
            "| rule | coverage | hidden_violation_rate | n_hidden_violation | "
            "mean_regret |"
        )
        lines.append("|---|---|---|---|---|")
        for name in _RULE_ORDER:
            r = rules.get(name)
            if r is None:
                continue
            lines.append(
                f"| {name} | {_fmt(r['coverage'])} | "
                f"{_fmt(r['hidden_violation_rate'])} | {r['n_hidden_violation']} | "
                f"{_fmt(r['mean_regret'])} |"
            )
        lines.append("")
        sel = m["selective_hidden_violation_rate"]
        beat = m["must_beat_hidden_violation_rate"]
        beat_str = ", ".join(f"{k}={_fmt(v)}" for k, v in beat.items())
        verdict = m["c2_verdict"]
        if verdict == "no-bite":
            lines.append(
                f"**C2 verdict (NO-BITE):** no must-beat baseline violates the masked "
                f"truth here — [{beat_str}] (nothing to beat)."
            )
        else:
            lines.append(
                f"**C2 verdict ({verdict.upper()}):** selective hidden-violation = "
                f"{_fmt(sel)} vs [{beat_str}]."
            )
        lines.append("")
        if block["significance"]:
            lines.append(
                "| baseline | n | mean_diff (base−sel) | 95% CI | McNemar b/c | "
                "binom p (1-sided) | significant |"
            )
            lines.append("|---|---|---|---|---|---|---|")
            for name, s in block["significance"].items():
                lines.append(
                    f"| {name} | {s['n']} | {_fmt(s['mean_diff'])} | "
                    f"[{_fmt(s['ci95_lo'])}, {_fmt(s['ci95_hi'])}] | "
                    f"{s['mcnemar_b']}/{s['mcnemar_c']} | {s['binom_p_one_sided']:.2e} | "
                    f"{'YES' if s['significant'] else 'no'} |"
                )
            lines.append("")

    # ---- pooled significance ----
    def _pooled_table(pooled: dict) -> None:
        lines.append(
            "| baseline | n | HV(baseline) | HV(selective) | difference | 95% CI | "
            "CI excl. 0 | binom p | significant |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for name in meta["must_beat"]:
            p = pooled.get(name, {})
            if p.get("n", 0) == 0:
                lines.append(f"| {name} | 0 | — | — | — | — | — | — | — |")
                continue
            lines.append(
                f"| {name} | {p['n']} | {_fmt(p['baseline_hidden_violation_rate'])} | "
                f"{_fmt(p['selective_hidden_violation_rate'])} | "
                f"{_fmt(p['mean_diff'])} | "
                f"[{_fmt(p['ci95_lo'])}, {_fmt(p['ci95_hi'])}] | "
                f"{'yes' if p['ci_excludes_zero'] else 'no'} | "
                f"{p['binom_p_one_sided']:.2e} | "
                f"{'YES' if p['significant'] else 'no'} |"
            )
        lines.append("")

    lines.append("## Pooled significance (ALL biting slices)")
    lines.append("")
    lines.append(
        "Per-query paired comparison pooled across ALL biting slices (H + M "
        "confidence): for each query does the baseline hidden-violate while "
        "selective does not? Difference = baseline − selective "
        "hidden-violation-rate; bootstrap 95% CI seeded "
        f"(random.Random({meta['seed']})); McNemar one-sided exact binomial on the "
        "discordant pairs."
    )
    lines.append("")
    _pooled_table(res["pooled"])

    lines.append("## Pooled significance — H-CONFIDENCE ONLY (FLAGSHIP)")
    lines.append("")
    lines.append(
        "The same pooled test restricted to H-confidence biting slices (the "
        "RouterBench per-benchmark slices with real measured ground truth), "
        "EXCLUDING the M-confidence BFCL slice. This is the flagship result: it "
        "does not depend on any M-confidence data, closing mock-review W5."
    )
    lines.append("")
    _pooled_table(res["pooled_h_only"])
    return "\n".join(lines)


def _print_summary(res: dict) -> None:
    meta = res["meta"]
    print("=" * 76)
    print(
        f"P5 VALIDATION SCALED  (provenance={PROVENANCE}, phi={PHI.value}, "
        f"kappa={'+'.join(KAPPA)}, seed={meta['seed']})"
    )
    print("=" * 76)
    print(
        f"slices={meta['n_slices']} ({meta['n_biting_slices']} biting, "
        f"{meta['n_biting_slices_h']} H-confidence), "
        f"total_queries={meta['total_queries']} "
        f"(biting={meta['biting_queries']}, H-biting={meta['biting_queries_h']})"
    )
    if meta.get("skipped_slices"):
        print(f"skipped (degenerate): {', '.join(meta['skipped_slices'])}")
    print("\nPer-slice C2 verdicts (hidden_violation_rate):")
    print(f"  {'slice':<48} {'B2':>5} {'B3':>5} {'sel':>5}  verdict")
    for key, block in res["slices"].items():
        m = block["meta"]
        beat = m["must_beat_hidden_violation_rate"]
        b2 = beat.get("B2_observed_pareto", float("nan"))
        b3 = beat.get("B3_imputation", float("nan"))
        sel = m["selective_hidden_violation_rate"]
        print(
            f"  {key:<48} {b2:>5.2f} {b3:>5.2f} {sel:>5.2f}  "
            f"{m['c2_verdict'].upper()}"
        )

    def _print_pooled(title: str, pooled: dict) -> None:
        print("\n" + "-" * 76)
        print(title)
        for name in meta["must_beat"]:
            p = pooled.get(name, {})
            if p.get("n", 0) == 0:
                print(f"  {name}: no biting data")
                continue
            print(
                f"  {name}:  n={p['n']}  "
                f"HV(base)={p['baseline_hidden_violation_rate']:.3f}  "
                f"HV(sel)={p['selective_hidden_violation_rate']:.3f}  "
                f"diff={p['mean_diff']:.3f}  "
                f"95%CI=[{p['ci95_lo']:.3f}, {p['ci95_hi']:.3f}]  "
                f"p={p['binom_p_one_sided']:.2e}  "
                f"significant={'YES' if p['significant'] else 'no'}"
            )

    _print_pooled(
        "POOLED significance across ALL biting slices (baseline vs selective):",
        res["pooled"],
    )
    _print_pooled(
        "POOLED significance — H-CONFIDENCE ONLY [FLAGSHIP] (baseline vs selective):",
        res["pooled_h_only"],
    )
    print("=" * 76)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)

    res = runner.scale_v1(seed=SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "seed": SEED,
        },
        "scale_v1": res,
    }
    json_path = OUT_DIR / "validation_scaled.json"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8"
    )
    md_path = OUT_DIR / "validation_scaled.md"
    md_path.write_text(_render_md(res), encoding="utf-8")

    _print_summary(res)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
