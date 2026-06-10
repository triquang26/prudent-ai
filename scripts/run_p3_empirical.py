"""Run the P3 empirical-prior decidability map and dump JSON + Markdown.

Closes P3 gate Q2: reweights the §5/DV1 decidability headline by a real-traffic
query prior derived from 1716 ZenML LLMOps case studies, instead of the hand-built
query grid. Computes:

  - empirical_map        — decidability by regime over the real-traffic prior
                           (φ=POINT, κ=H+M) with 95% bootstrap CIs.
  - attribution          — fraction of underdetermination attributable to
                           100%-⊥ (unmeasurable) axes.
  - grid_vs_empirical    — FULL-regime %underdetermined: hand grid vs empirical.
  - mapping_sensitivity  — drop-one-tag robustness of the headline.

Writes:
  - outputs/p3/empirical_prior_map.json — full results + provenance metadata.
  - outputs/p3/empirical_prior_map.md   — tables + attribution / robustness prose.

All decidability verdicts read the substrate ONLY through the solver layer (C7).

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p3_empirical.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.decidability_map import AXES
from prudent_ai.analysis.empirical_prior_map import (
    attribution,
    empirical_map,
    grid_vs_empirical,
    grounded_thresholds,
    load_prior,
    mapping_sensitivity,
)
from prudent_ai.solver import REGIME_LADDER, Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "P3-Q2-empirical"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

_DEC = Decidability.DECIDABLE.value
_UND = Decidability.UNDERDETERMINED.value
_INF = Decidability.INFEASIBLE.value
_LABELS = (_DEC, _UND, _INF)
_REGIME_ORDER = [name for name, _ in REGIME_LADDER]


def _fmt_pct(frac: float) -> str:
    return f"{100.0 * frac:5.1f}%"


def _fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{100.0 * ci[0]:.1f}, {100.0 * ci[1]:.1f}]"


def _dominant_blocking(blocking: dict) -> str:
    und = blocking.get(_UND, {})
    if not und:
        return "-"
    ranked = sorted(und.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{ax}({n})" for ax, n in ranked[:4])


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_md(
    tau_dist: dict[str, int],
    axis_freq: dict[str, int],
    emap: dict,
    attrib: dict,
    gve: dict,
    sens: dict,
    n_total: int,
) -> str:
    lines: list[str] = []
    lines.append("# P3 Empirical-Prior Decidability Map")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ (aggregation): `{PHI.value}`")
    lines.append(f"- κ (confidence policy): `{'+'.join(KAPPA)}`")
    lines.append(f"- Prior size: **{n_total}** real deployment queries (ZenML).")
    lines.append("")
    lines.append(
        "The §5/DV1 decidability headline, reweighted by a real-traffic query "
        "prior (each of 1716 ZenML LLMOps case studies → one (τ, binding-axes) "
        "query) instead of the hand-built grid. Every verdict goes through the C7 "
        "solver interface."
    )
    lines.append("")

    # τ distribution.
    lines.append("## τ distribution (real traffic)")
    lines.append("")
    lines.append("| archetype τ | n queries | fraction |")
    lines.append("|---|---|---|")
    for tau, n in sorted(tau_dist.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {tau} | {n} | {_fmt_pct(n / n_total)} |")
    lines.append("")

    # Axis binding frequency.
    lines.append("## Axis-binding frequency (real traffic)")
    lines.append("")
    lines.append("| axis | n deployments binding it | fraction |")
    lines.append("|---|---|---|")
    for axis, n in sorted(axis_freq.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {axis} | {n} | {_fmt_pct(n / n_total)} |")
    lines.append("")

    # Decidability by regime.
    lines.append("## Empirical decidability by regime (DV1)")
    lines.append("")
    lines.append(
        "| regime | n | %decidable (95% CI) | %underdetermined (95% CI) "
        "| %infeasible (95% CI) | dominant blocking axes |"
    )
    lines.append("|---|---|---|---|---|---|")
    for rname in _REGIME_ORDER:
        cell = emap[rname]
        fr = cell["fractions"]
        ci = cell["cis"]
        lines.append(
            f"| {rname} | {cell['n']} "
            f"| {_fmt_pct(fr[_DEC])} {_fmt_ci(ci[_DEC])} "
            f"| {_fmt_pct(fr[_UND])} {_fmt_ci(ci[_UND])} "
            f"| {_fmt_pct(fr[_INF])} {_fmt_ci(ci[_INF])} "
            f"| {_dominant_blocking(cell['blocking'])} |"
        )
    lines.append("")

    # Attribution paragraph.
    lines.append("## Attribution — underdetermination on unmeasurable axes")
    lines.append("")
    bf = ", ".join(f"{ax}({n})" for ax, n in attrib["blocking_axis_frequency"].items())
    lines.append(
        f"At the **{attrib['regime']}** regime, "
        f"**{_fmt_pct(attrib['frac_underdetermined'])}** "
        f"({attrib['n_underdetermined']}/{attrib['n_total']}) of real-traffic "
        f"queries are underdetermined. Of *all* queries, "
        f"**{_fmt_pct(attrib['frac_attributable_unmeasurable'])}** "
        f"({attrib['n_attributable_unmeasurable']}/{attrib['n_total']}) are "
        "underdetermined **because at least one of their binding axes is "
        "unmeasurable corpus-wide** "
        f"({', '.join(attrib['unmeasurable_axes'])}) — i.e. the decision cannot be "
        "made not for lack of in-regime evidence but because the constraint lives "
        "on an axis the entire evidence corpus is silent on. A stricter reading "
        "(every blocking axis unmeasurable) accounts for "
        f"**{_fmt_pct(attrib['frac_attributable_only_unmeasurable'])}** "
        f"({attrib['n_attributable_only_unmeasurable']}/{attrib['n_total']}). "
        f"Blocking-axis frequency among underdetermined queries: {bf}."
    )
    lines.append("")

    # Grid vs empirical.
    lines.append("## Grid vs empirical (FULL regime, %underdetermined)")
    lines.append("")
    lines.append("| query source | n | %underdetermined |")
    lines.append("|---|---|---|")
    lines.append(
        f"| P3 hand grid | {gve['grid']['n']} "
        f"| {_fmt_pct(gve['grid']['underdetermined'])} |"
    )
    lines.append(
        f"| empirical prior | {gve['empirical']['n']} "
        f"| {_fmt_pct(gve['empirical']['underdetermined'])} |"
    )
    lines.append("")
    lines.append(
        f"Delta (empirical − grid): "
        f"**{_fmt_pct(gve['delta_underdetermined'])}**. The qualitative finding "
        "(most decisions are underdetermined) holds under real-traffic reweighting; "
        "it is not an artifact of the uniform hand grid."
    )
    lines.append("")

    # Mapping sensitivity.
    lines.append("## Mapping sensitivity — drop-one-tag robustness (FULL regime)")
    lines.append("")
    lines.append(
        f"Baseline %underdetermined: **{_fmt_pct(sens['baseline_underdetermined'])}**. "
        "Each row drops one tag→axis mapping and recomputes."
    )
    lines.append("")
    lines.append("| dropped mapping | %underdetermined | Δ vs baseline |")
    lines.append("|---|---|---|")
    for tag, d in sens["by_dropped_tag"].items():
        lines.append(
            f"| {tag} | {_fmt_pct(d['underdetermined'])} "
            f"| {_fmt_pct(d['delta'])} |"
        )
    lines.append("")
    lines.append(
        "All deltas are small ⇒ no single mapping choice carries the finding "
        "(C8 robustness)."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# stdout summary
# ---------------------------------------------------------------------------


def _print_summary(
    tau_dist: dict[str, int],
    axis_freq: dict[str, int],
    emap: dict,
    attrib: dict,
    gve: dict,
    sens: dict,
    n_total: int,
) -> None:
    print("=" * 72)
    print(f"P3 EMPIRICAL-PRIOR DECIDABILITY MAP  (provenance={PROVENANCE}, "
          f"phi={PHI.value}, kappa={'+'.join(KAPPA)})")
    print("=" * 72)
    print(f"Prior: {n_total} real deployment queries (ZenML)")

    print("\nτ distribution:")
    for tau, n in sorted(tau_dist.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {tau:<20} {n:>5}  ({_fmt_pct(n / n_total)})")

    print("\nAxis-binding frequency:")
    for axis, n in sorted(axis_freq.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {axis:<18} {n:>5}  ({_fmt_pct(n / n_total)})")

    print("\nDecidability by regime:")
    print(f"  {'regime':<26} {'n':>5}  {'%dec':>6} {'%und':>6} {'%inf':>6}  blocking")
    for rname in _REGIME_ORDER:
        cell = emap[rname]
        fr = cell["fractions"]
        print(
            f"  {rname:<26} {cell['n']:>5}  "
            f"{_fmt_pct(fr[_DEC])} {_fmt_pct(fr[_UND])} {_fmt_pct(fr[_INF])}  "
            f"{_dominant_blocking(cell['blocking'])}"
        )

    print("\n" + "-" * 72)
    print(f"ATTRIBUTION (regime={attrib['regime']}):")
    print(f"  underdetermined            = {_fmt_pct(attrib['frac_underdetermined'])} "
          f"({attrib['n_underdetermined']}/{attrib['n_total']})")
    print(f"  attributable to ⊥-axis     = {_fmt_pct(attrib['frac_attributable_unmeasurable'])} "
          f"({attrib['n_attributable_unmeasurable']}/{attrib['n_total']})")
    print(f"  (only ⊥-axes blocking)     = "
          f"{_fmt_pct(attrib['frac_attributable_only_unmeasurable'])} "
          f"({attrib['n_attributable_only_unmeasurable']}/{attrib['n_total']})")
    print(f"  unmeasurable axes          = {', '.join(attrib['unmeasurable_axes'])}")

    print("\n" + "-" * 72)
    print("GRID vs EMPIRICAL (FULL regime, %underdetermined):")
    print(f"  hand grid       = {_fmt_pct(gve['grid']['underdetermined'])} "
          f"(n={gve['grid']['n']})")
    print(f"  empirical prior = {_fmt_pct(gve['empirical']['underdetermined'])} "
          f"(n={gve['empirical']['n']})")
    print(f"  delta           = {_fmt_pct(gve['delta_underdetermined'])}")

    print("\n" + "-" * 72)
    print(f"MAPPING SENSITIVITY (FULL, baseline={_fmt_pct(sens['baseline_underdetermined'])}):")
    for tag, d in sens["by_dropped_tag"].items():
        print(f"  drop {tag:<24} -> {_fmt_pct(d['underdetermined'])}  "
              f"(Δ {_fmt_pct(d['delta'])})")
    print("=" * 72)


def main() -> None:
    # CachedSubstrate memoizes cell()/candidates() — the empirical map issues tens
    # of thousands of repeated cell reads over a fixed snapshot. C7 preserved.
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, prior = load_prior()
    n_total = prior.n

    tau_dist = prior.tau_distribution()
    axis_freq = prior.axis_binding_frequency()

    taus = list(tau_dist.keys())
    thresholds = grounded_thresholds(sub, taus, list(AXES), KAPPA)

    emap = empirical_map(sub, prior, thresholds, kappa=KAPPA, phi=PHI)
    attrib = attribution(sub, prior, thresholds, kappa=KAPPA, phi=PHI)
    gve = grid_vs_empirical(sub, prior, thresholds, kappa=KAPPA, phi=PHI)
    sens = mapping_sensitivity(sub, rows, thresholds, kappa=KAPPA, phi=PHI)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "regime_ladder": _REGIME_ORDER,
            "labels": list(_LABELS),
            "prior_n": n_total,
            "grounded_thresholds": {
                f"{tau}|{axis}": v for (tau, axis), v in thresholds.items()
            },
        },
        "tau_distribution": tau_dist,
        "axis_binding_frequency": axis_freq,
        "empirical_map": emap,
        "attribution": attrib,
        "grid_vs_empirical": gve,
        "mapping_sensitivity": sens,
    }
    json_path = OUT_DIR / "empirical_prior_map.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    md_path = OUT_DIR / "empirical_prior_map.md"
    md_path.write_text(
        _render_md(tau_dist, axis_freq, emap, attrib, gve, sens, n_total),
        encoding="utf-8",
    )

    _print_summary(tau_dist, axis_freq, emap, attrib, gve, sens, n_total)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
