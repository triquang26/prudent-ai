"""Execute the full P3 decidability map and dump JSON + Markdown artifacts.

Runs the §5/DV1 decidability map (φ=POINT, κ=H+M), the H2 descriptive blind-spot
report, and the H3 κ-sensitivity sweep over the APT substrate, then writes:

  - outputs/p3/decidability_map.json — full nested results + a metadata block.
  - outputs/p3/decidability_map.md   — human-readable tables + sensitivity paragraph.

The decidability computation reads the substrate ONLY through the solver layer
(C7 firewall). The blind-spot report is descriptive and labelled as such by the
analysis module.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p3_map.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.decidability_map import (
    blind_spot_report,
    build_map,
    sensitivity_kappa,
)
from prudent_ai.solver import REGIME_LADDER, Decidability, Phi
from prudent_ai.solver.beliefs import DEFAULT_KAPPA
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
SNAPSHOT = "P3-run"

# Stable label ordering for tables / JSON.
_DEC = Decidability.DECIDABLE.value
_UND = Decidability.UNDERDETERMINED.value
_INF = Decidability.INFEASIBLE.value
_LABELS = (_DEC, _UND, _INF)

_REGIME_ORDER = [name for name, _ in REGIME_LADDER]


def _dominant_blocking(blocking: dict) -> str:
    """Top blocking axes (from the UNDERDETERMINED tally) as a compact string."""
    und = blocking.get(_UND, {})
    if not und:
        return "-"
    ranked = sorted(und.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{ax}({n})" for ax, n in ranked[:3])


def _fmt_pct(frac: float) -> str:
    return f"{100.0 * frac:5.1f}%"


def _fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{100.0 * ci[0]:.1f}, {100.0 * ci[1]:.1f}]"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_md(dmap: dict, blind: dict, sens: dict, kappa: tuple[str, ...]) -> str:
    lines: list[str] = []
    lines.append("# P3 Decidability Map")
    lines.append("")
    lines.append(f"- Snapshot: `{SNAPSHOT}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ (aggregation): `{Phi.POINT.value}`")
    lines.append(f"- κ (confidence policy): `{'+'.join(kappa)}`")
    lines.append("")
    lines.append(
        "DV1 (§5): per (archetype τ × evidence-regime R) cell, the fraction of the "
        "structured query battery that is decidable / underdetermined / infeasible, "
        "with 95% bootstrap CIs and the dominant blocking axes (from the "
        "underdetermined tally)."
    )
    lines.append("")

    # One table per archetype.
    for tau, regimes in dmap.items():
        lines.append(f"## τ = {tau}")
        lines.append("")
        lines.append(
            "| regime | n | %decidable (95% CI) | %underdetermined (95% CI) "
            "| %infeasible (95% CI) | dominant blocking axes |"
        )
        lines.append("|---|---|---|---|---|---|")
        for rname in _REGIME_ORDER:
            cell = regimes.get(rname)
            if cell is None:
                continue
            fr = cell["fractions"]
            ci = cell["cis"]
            n = sum(cell["counts"].values())
            lines.append(
                f"| {rname} | {n} "
                f"| {_fmt_pct(fr[_DEC])} {_fmt_ci(ci[_DEC])} "
                f"| {_fmt_pct(fr[_UND])} {_fmt_ci(ci[_UND])} "
                f"| {_fmt_pct(fr[_INF])} {_fmt_ci(ci[_INF])} "
                f"| {_dominant_blocking(cell['blocking'])} |"
            )
        lines.append("")

    # Blind-spot table (descriptive, H2).
    lines.append("## Blind-spot miss-rates (descriptive — H2)")
    lines.append("")
    lines.append(
        f"Provenance: `{blind['provenance']}`. Miss-rate of axis a = fraction of "
        f"configs with zero κ-qualifying observation on a (κ = {'+'.join(blind['kappa'])}). "
        "This is a coverage statistic over the raw DB and never feeds a verdict."
    )
    lines.append("")
    taus = list(blind["per_tau"].keys())
    header = "| axis | " + " | ".join(taus) + " | overall |"
    sep = "|---|" + "|".join("---" for _ in taus) + "|---|"
    lines.append(header)
    lines.append(sep)
    # Axis order from the overall dict (stable AXES order).
    for axis in blind["overall"]:
        cells = [_fmt_pct(blind["per_tau"][t][axis]) for t in taus]
        lines.append(
            f"| {axis} | " + " | ".join(cells) + f" | {_fmt_pct(blind['overall'][axis])} |"
        )
    lines.append("")
    cc = blind["config_counts"]
    counts_str = ", ".join(f"{t}={cc[t]}" for t in taus) + f", total={cc['__total__']}"
    lines.append(f"Config counts: {counts_str}.")
    lines.append("")

    # κ-sensitivity paragraph (H3).
    lines.append("## κ-sensitivity (H3)")
    lines.append("")
    bk = sens["by_kappa"]

    def _u(key: str) -> str:
        return _fmt_pct(bk[key]["underdetermined_overall"]) if key in bk else "n/a"

    lines.append(
        "Overall underdetermined-fraction (averaged over all τ × regime cells), as "
        "the confidence policy is tightened/loosened:"
    )
    lines.append("")
    lines.append(
        f"- **H** (`H`): {_u('H')}\n"
        f"- **H+M** (`H+M`): {_u('H+M')}\n"
        f"- **H+M+L** (`H+M+L`): {_u('H+M+L')}"
    )
    lines.append("")
    lines.append(
        "Looser κ pools more (lower-confidence) observations, which can resolve some "
        "underdetermined queries (evidence appears) while re-grounding the grid "
        "thresholds; the shift above quantifies that net effect."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# stdout summary
# ---------------------------------------------------------------------------


def _print_summary(dmap: dict, blind: dict, sens: dict, kappa: tuple[str, ...]) -> None:
    print("=" * 72)
    print(f"P3 DECIDABILITY MAP  (snapshot={SNAPSHOT}, phi={Phi.POINT.value}, "
          f"kappa={'+'.join(kappa)})")
    print("=" * 72)
    for tau, regimes in dmap.items():
        print(f"\nτ = {tau}")
        print(f"  {'regime':<26} {'n':>3}  {'%dec':>6} {'%und':>6} {'%inf':>6}  blocking")
        for rname in _REGIME_ORDER:
            cell = regimes.get(rname)
            if cell is None:
                continue
            fr = cell["fractions"]
            n = sum(cell["counts"].values())
            print(
                f"  {rname:<26} {n:>3}  "
                f"{_fmt_pct(fr[_DEC])} {_fmt_pct(fr[_UND])} {_fmt_pct(fr[_INF])}  "
                f"{_dominant_blocking(cell['blocking'])}"
            )

    print("\n" + "-" * 72)
    print(f"BLIND-SPOT miss-rates (descriptive, kappa={'+'.join(blind['kappa'])})")
    print("-" * 72)
    taus = list(blind["per_tau"].keys())
    print(f"  {'axis':<18} " + " ".join(f"{t[:14]:>14}" for t in taus) + f" {'overall':>9}")
    for axis in blind["overall"]:
        row = " ".join(f"{_fmt_pct(blind['per_tau'][t][axis]):>14}" for t in taus)
        print(f"  {axis:<18} {row} {_fmt_pct(blind['overall'][axis]):>9}")

    print("\n" + "-" * 72)
    print("κ-SENSITIVITY (H3) — overall underdetermined-fraction")
    print("-" * 72)
    bk = sens["by_kappa"]
    for key in ("H", "H+M", "H+M+L"):
        if key in bk:
            print(f"  {key:<8} -> underdetermined = {_fmt_pct(bk[key]['underdetermined_overall'])}")
    print("=" * 72)


def main() -> None:
    kappa = DEFAULT_KAPPA  # ('H', 'M')
    sub = Substrate(DB_PATH)

    dmap = build_map(sub, kappa=kappa, phi=Phi.POINT)
    blind = blind_spot_report(sub, kappa=kappa)
    sens = sensitivity_kappa(sub, phi=Phi.POINT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON artifact: full nested results + metadata block.
    payload = {
        "metadata": {
            "snapshot": SNAPSHOT,
            "db_path": DB_PATH,
            "phi": Phi.POINT.value,
            "kappa": list(kappa),
            "regime_ladder": _REGIME_ORDER,
            "labels": list(_LABELS),
        },
        "decidability_map": dmap,
        "blind_spot_report": blind,
        "sensitivity_kappa": sens,
    }
    json_path = OUT_DIR / "decidability_map.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    md_path = OUT_DIR / "decidability_map.md"
    md_path.write_text(_render_md(dmap, blind, sens, kappa), encoding="utf-8")

    _print_summary(dmap, blind, sens, kappa)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
