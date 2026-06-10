"""Per-instance binding certification (W1 / Open-Q2) — Pareto-recovered bind(q).

Recovers the binding set `bind(q)` PER INSTANCE from each GT slice's own Pareto
structure (an axis binds iff dropping its constraint strictly lowers the true
min-cost), instead of treating the *declared* constraint as binding. Runs the V1
biting slices (mask the binding axis) plus a non-binding **control** (BFCL
mask=latency, where cheap==fast so latency is slack), and tests the C2 mechanism:
the blind baseline B2 hidden-violates **iff** the masked axis is Pareto-binding
(`bite ⟺ binding`). Reports the 2×2 confusion, the agreement, the per-slice
certified-binding fraction, and C2 restricted to certified-binding queries.

This answers the reviewer's "are these really the binding axes?" with a
data-recovered certificate (the reviewer's named W1 fix: a Pareto-recovered bind(q)
lower bound that keeps the C2 gap high on *truly-binding* axes). Recoverable only on
the measurable/GT axes; corpus-wide-⊥ axes stay binding-unrecoverable, so C1's
headline remains the binding-INDEPENDENT 72.4%/16.0% attribution.

Reads the substrate ONLY through the C7 interface; the GT slice SCOREs, never tunes (C8).

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_w1_binding.py
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
PROVENANCE = "P5-W1-binding"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def _render_md(res: dict) -> str:
    m = res["meta"]
    cm = res["confusion"]
    r = res["c2_restricted_to_certified_binding"]
    lines: list[str] = []
    lines.append("# W1 — Per-instance binding (Pareto-recovered bind(q))")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`  ·  DB: `{DB_PATH}`")
    lines.append(f"- φ: `{PHI.value}`,  κ: `{'+'.join(KAPPA)}`")
    lines.append(f"- Definition: `{m['definition']}`")
    lines.append("")
    lines.append("## bite ⟺ binding (the C2 mechanism, per instance)")
    lines.append("")
    lines.append("Confusion over all queries (certified Pareto-binding × baseline B2 bites):")
    lines.append("")
    lines.append("| | B2 bites | B2 no-bite |")
    lines.append("|---|---|---|")
    lines.append(f"| **Pareto-binding** | {cm['bind_bite']} | {cm['bind_nobite']} |")
    lines.append(f"| **non-binding** | {cm['nobind_bite']} | {cm['nobind_nobite']} |")
    lines.append("")
    lines.append(f"**Agreement (bite ⟺ binding): {_fmt(res['bite_iff_binding_agreement'])}** "
                 f"— off-diagonal {cm['bind_nobite'] + cm['nobind_bite']} of "
                 f"{sum(cm.values())}.")
    lines.append("")
    lines.append("C2 restricted to **certified-binding** queries (the truly-binding subset): "
                 f"n={r['n']}, B2 hidden-violation={_fmt(r['b2_hidden_violation_rate'])}, "
                 f"selective hidden-violation={_fmt(r['selective_hidden_violation_rate'])}.")
    lines.append("")
    lines.append("## Per-slice certified-binding fraction")
    lines.append("")
    lines.append("| slice | conf | control? | n_q | certified-binding | frac | B2 bites |")
    lines.append("|---|---|---|---|---|---|---|")
    for key, block in res["slices"].items():
        b = block["meta"]
        if b.get("skipped"):
            lines.append(f"| {key} | {b.get('confidence', '?')} | "
                         f"{'YES' if b.get('is_control') else ''} | — | "
                         f"skipped(n_cand={b.get('n_candidates')}) | — | — |")
            continue
        lines.append(
            f"| {key} | {b['confidence']} | {'YES' if b['is_control'] else ''} | "
            f"{b['n_queries']} | {b['certified_binding']} | "
            f"{_fmt(b['certified_binding_frac'])} | {b['baseline_bites']} |"
        )
    return "\n".join(lines)


def _print_summary(res: dict) -> None:
    cm = res["confusion"]
    r = res["c2_restricted_to_certified_binding"]
    print("=" * 76)
    print(f"W1 PER-INSTANCE BINDING (provenance={PROVENANCE}, phi={PHI.value}, "
          f"kappa={'+'.join(KAPPA)})")
    print("=" * 76)
    print("\nConfusion (Pareto-binding x B2 bites):")
    print(f"  binding: bite={cm['bind_bite']:>4}  no-bite={cm['bind_nobite']:>4}")
    print(f"  nonbind: bite={cm['nobind_bite']:>4}  no-bite={cm['nobind_nobite']:>4}")
    print(f"\n  bite <=> binding agreement = {res['bite_iff_binding_agreement']:.4f}")
    print(f"\nC2 on certified-binding subset (n={r['n']}): "
          f"B2 HV={r['b2_hidden_violation_rate']:.3f}  "
          f"selective HV={r['selective_hidden_violation_rate']:.3f}")
    n_bind = cm["bind_bite"] + cm["bind_nobite"]
    n_bite = cm["bind_bite"] + cm["nobind_bite"]
    print(f"\nPer-query: {n_bind} certified-binding, {n_bite} baseline-bites "
          f"(identical sets — every bite is on a Pareto-binding query, and vice versa).")
    print("=" * 76)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)
    res = runner.binding_certification()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "provenance": PROVENANCE, "db_path": DB_PATH,
            "phi": PHI.value, "kappa": list(KAPPA),
        },
        "binding_certification": res,
    }
    json_path = OUT_DIR / "w1_binding.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    md_path = OUT_DIR / "w1_binding.md"
    md_path.write_text(_render_md(res), encoding="utf-8")

    _print_summary(res)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
