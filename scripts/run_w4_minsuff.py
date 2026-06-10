"""Min-sufficiency guarantee via a two-sided band (W4 residual) — real GT.

Closes the W4 residual: the feasibility guarantee (`run_p4_guarantee_gt.py`) calibrates
only the §9 *safety* half; min-sufficiency was a one-sided-margin-uncontrollable
diagnostic (test min-suff risk 65.8% at the α=0.05 feasibility margin). With a second,
two-sided **band** knob `b` — abstain when a strictly-cheaper config is plausibly
feasible — min-sufficiency becomes calibratable: jointly tuning `(m, b)` on a held-out
real-GT split guarantees **test min-sufficiency risk ≤ α**, at a quantified coverage cost.

Writes:
  - outputs/p4/minsuff_guarantee.json — band curve + per-α (m,b) calibration + provenance.
  - outputs/p4/minsuff_guarantee.md   — the band-sweep + the guaranteed-min-suff table.

Truth = full-sample per-prompt RouterBench; operating = seeded subsample (C8 disjoint
calib/test). Direct pkl scoring → C7 not engaged.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_w4_minsuff.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from prudent_ai.validation.minsuff_guarantee import (
    DEFAULT_BANDS,
    DEFAULT_MARGINS,
    MinSuffGuarantee,
)

OUT_DIR = Path("outputs/p4")
PROVENANCE = "P4-minsuff-band"
ALPHAS = (0.05, 0.10, 0.20)
SPLIT_SEED = 2024
# margin held at the feasibility-calibrated value while sweeping the band, to isolate
# the band's effect on min-sufficiency.
SWEEP_MARGIN = 0.05


def _pct(x: float) -> str:
    return f"{100.0 * x:5.1f}%"


def _render_md(g, band_sweep, calibs, n_total) -> str:
    L: list[str] = []
    L.append("# P4 — Min-sufficiency guarantee via a two-sided band (W4 residual)\n")
    L.append(
        "The feasibility guarantee (`coverage_risk_gt.md`) controls P(commit feasible) "
        "with a one-sided quality margin `m`, but a larger `m` *over-provisions* and so "
        "**raises** min-sufficiency risk — a single knob cannot guarantee a two-sided "
        "(feasible ∧ cheapest) criterion. We add a second, two-sided **band** `b`: after "
        "selecting the min-noisy-cost eligible config, commit only if **no strictly "
        "cheaper config is plausibly feasible** (noisy_q ≥ q*−b), else abstain. Larger "
        "`b` ⇒ confidently-min-sufficient commits, lower coverage.\n"
    )
    L.append(f"- pkl: `{g.pkl_path}`  ·  models: **{len(g.benchmarks)} benchmarks**, "
             f"K={g.k_subsample}, seeds={g.n_seeds}")
    L.append(f"- total decision instances n = **{n_total}** (C8 disjoint 50/50 calib/test)")
    L.append("- cost tolerance for min-sufficiency: relative, as `gt_guarantee.COST_TOL`")
    L.append("")
    L.append(f"## Band sweep at fixed margin m={SWEEP_MARGIN} (full battery)\n")
    L.append("| band b | coverage | feas. risk | **min-suff. risk** | n_commit | n_min_suff |")
    L.append("|---|---|---|---|---|---|")
    for p in band_sweep:
        L.append(
            f"| {p.band:g} | {_pct(p.coverage)} | {_pct(p.risk_feasible)} | "
            f"**{_pct(p.risk_min_sufficient)}** | {p.n_commit} | {p.n_min_sufficient} |"
        )
    L.append("")
    L.append("As `b` grows, min-sufficiency risk falls (the band abstains whenever a "
             "cheaper config might be the true minimum) at the cost of coverage, until the "
             "very widest bands collapse coverage to a small, noisy tail. The calibration "
             "below picks the best (m,b) on calib, so it sits in the useful regime — the "
             "missing W4 knob, now present.\n")
    L.append("## Calibrated MIN-SUFFICIENCY guarantee — (m,b) on calib, on TEST\n")
    L.append("| α | margin m | band b | calib cov | **test cov** | test feas-risk | "
             "**test min-suff risk** | test n_commit | holds? |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in calibs:
        ms = "—" if c.margin is None else f"{c.margin:g}"
        bs = "—" if c.band is None else f"{c.band:g}"
        holds = "✅" if (c.band is not None and c.test_risk_min_sufficient <= c.alpha) else "⚠"
        L.append(
            f"| {c.alpha:g} | {ms} | {bs} | {_pct(c.calib_coverage)} | "
            f"**{_pct(c.test_coverage)}** | {_pct(c.test_risk_feasible)} | "
            f"**{_pct(c.test_risk_min_sufficient)}** | {c.test_n_commit} | {holds} |"
        )
    L.append("")
    L.append("*holds?* = the calibrated (m,b) yields **test min-sufficiency risk ≤ α** on "
             "the held-out split — the full §9 *feasible ∧ minimum-sufficient* guarantee, "
             "now transferred to real held-out GT (closing the W4 residual). The coverage "
             "is lower than the feasibility-only guarantee: that gap is the honest price of "
             "the stronger two-sided criterion.")
    return "\n".join(L)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    g = MinSuffGuarantee()
    print("[load] per-prompt RouterBench truth + decision battery...")
    outs = g.generate_outcomes()
    calib, test = g.split(outs, SPLIT_SEED)
    print(f"[battery] {len(outs)} instances; calib {len(calib)} / test {len(test)}")

    band_sweep = [g.band_point(outs, SWEEP_MARGIN, b) for b in DEFAULT_BANDS]
    calibs = [g.calibrate_min_sufficient(calib, test, a, DEFAULT_MARGINS, DEFAULT_BANDS)
              for a in ALPHAS]

    payload = {
        "metadata": {"provenance": PROVENANCE, "pkl": g.pkl_path,
                     "alphas": list(ALPHAS), "split_seed": SPLIT_SEED,
                     "sweep_margin": SWEEP_MARGIN, "n_total": len(outs)},
        "band_sweep": [asdict(p) for p in band_sweep],
        "calibrations": [asdict(c) for c in calibs],
    }
    (OUT_DIR / "minsuff_guarantee.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "minsuff_guarantee.md").write_text(
        _render_md(g, band_sweep, calibs, len(outs)), encoding="utf-8")

    print("=" * 76)
    print("W4 RESIDUAL — min-sufficiency guarantee via two-sided band")
    print("=" * 76)
    for c in calibs:
        holds = "YES" if (c.band is not None and c.test_risk_min_sufficient <= c.alpha) else "no"
        print(f"  alpha={c.alpha:<5} m={c.margin} b={c.band}  "
              f"test cov={c.test_coverage:.3f}  "
              f"test min-suff risk={c.test_risk_min_sufficient:.3f}  holds={holds}")
    print("=" * 76)
    print(f"Wrote {OUT_DIR / 'minsuff_guarantee.json'}")
    print(f"Wrote {OUT_DIR / 'minsuff_guarantee.md'}")


if __name__ == "__main__":
    main()
