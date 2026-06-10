"""Run the P4 selective-procedure evaluation and dump JSON + Markdown.

Runs `procedure.right_size` over the empirical real-traffic query battery (1716
ZenML-derived queries) and summarizes the procedure's behaviour:

  - action rates (commit = coverage; abstain; infeasible).
  - acquire_next distribution: the axis the procedure says to measure next over the
    ABSTAIN queries (expected to concentrate on governance / reviewer_burden / cost).
  - top-blocking (highest-raw-VoI) axis distribution.
  - VoI-lift (§10 / P5 preview): does measuring the top-VoI axis reduce decision
    regret more than measuring a random blocking axis?

Writes:
  - outputs/p4/procedure_eval.json — full results + provenance metadata.
  - outputs/p4/procedure_eval.md   — action-rate table, acquire-next table, VoI-lift.

Every verdict reads the substrate ONLY through the solver layer (C7). The substrate
is wrapped in CachedSubstrate so the ~1716-query battery does not re-hit SQLite.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p4_eval.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.procedure_eval import (
    ProcedureEvaluator,
    build_empirical_queries,
)
from prudent_ai.solver import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p4")
PROVENANCE = "P4-eval"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
VOI_SEED = 12345


def _fmt_pct(frac: float) -> str:
    return f"{100.0 * frac:5.1f}%"


def _render_md(summary: dict, lift: dict) -> str:
    n = summary["n"]
    ar = summary["action_rates"]
    counts = summary["counts"]
    lines: list[str] = []
    lines.append("# P4 Selective-Procedure Evaluation")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- Regime: `{summary['regime']}`")
    lines.append(f"- φ (aggregation): `{PHI.value}`")
    lines.append(f"- κ (confidence policy): `{'+'.join(KAPPA)}`")
    lines.append(f"- λ (violation penalty): `{summary['lam']}`")
    lines.append(f"- Battery: **{n}** real deployment queries (ZenML empirical prior).")
    lines.append("")
    lines.append(
        "The selective right-sizing procedure (`right_size`) run over the "
        "real-traffic query battery: each query is COMMITted, ABSTAINed-on (with a "
        "cost-aware VoI acquisition ranking), or declared INFEASIBLE. Every verdict "
        "goes through the C7 solver interface."
    )
    lines.append("")

    # Action rates.
    lines.append("## Action rates")
    lines.append("")
    lines.append("| action | n | fraction |")
    lines.append("|---|---|---|")
    lines.append(f"| COMMIT (coverage) | {counts['commit']} | {_fmt_pct(ar['commit'])} |")
    lines.append(f"| ABSTAIN | {counts['abstain']} | {_fmt_pct(ar['abstain'])} |")
    lines.append(
        f"| INFEASIBLE | {counts['infeasible']} | {_fmt_pct(ar['infeasible'])} |"
    )
    lines.append("")
    lines.append(
        f"Coverage (commit rate) = **{_fmt_pct(summary['coverage'])}**; the "
        f"remaining **{_fmt_pct(ar['abstain'])}** abstain informatively."
    )
    lines.append("")

    # Acquire-next distribution.
    lines.append("## Acquire-next distribution (over abstentions)")
    lines.append("")
    lines.append(
        f"For each of the {summary['n_abstain']} ABSTAIN queries the procedure names "
        "the single axis to measure next (top VoI/cost). Distribution:"
    )
    lines.append("")
    lines.append("| axis to measure next | n | fraction of abstentions |")
    lines.append("|---|---|---|")
    n_ab = summary["n_abstain"]
    for axis, cnt in summary["acquire_next_distribution"].items():
        lines.append(f"| {axis} | {cnt} | {_fmt_pct(cnt / n_ab) if n_ab else '-'} |")
    lines.append("")

    # Top-blocking distribution.
    lines.append("## Top-blocking axis distribution (highest RAW VoI, over abstentions)")
    lines.append("")
    lines.append("| top-VoI blocking axis | n | fraction of abstentions |")
    lines.append("|---|---|---|")
    for axis, cnt in summary["top_blocking_distribution"].items():
        lines.append(f"| {axis} | {cnt} | {_fmt_pct(cnt / n_ab) if n_ab else '-'} |")
    lines.append("")
    lines.append(
        f"Mean top VoI over abstentions = **{summary['mean_top_voi']:.4f}**; "
        f"mean VoI-per-cost of the chosen axis = "
        f"**{summary['mean_voi_per_cost']:.4f}**."
    )
    lines.append("")

    # VoI lift.
    lines.append("## VoI lift (§10 — VoI predicts the field worth measuring)")
    lines.append("")
    ratio = lift["lift_ratio"]
    ratio_str = f"{ratio:.2f}x" if ratio is not None else "n/a"
    ca = lift["cost_aware"]
    ca_ratio = ca["lift_ratio"]
    ca_ratio_str = f"{ca_ratio:.2f}x" if ca_ratio is not None else "n/a"
    lines.append(
        f"Over the {lift['n_abstain_with_ranking']} abstentions with a VoI ranking "
        f"(seed={lift['seed']}): measuring the **top-VoI** axis reduces decision "
        f"regret by **{lift['mean_top_voi']:.4f}** on average, vs "
        f"**{lift['mean_random_voi']:.4f}** for a **random** blocking axis."
    )
    lines.append("")
    lines.append("| reading | baseline | top axis | random axis | lift | ratio |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| RAW VoI (field's regret reduction) | — "
        f"| {lift['mean_top_voi']:.4f} | {lift['mean_random_voi']:.4f} "
        f"| {lift['lift']:.4f} | {ratio_str} |"
    )
    lines.append(
        f"| COST-AWARE VoI/cost (acquisition key) | — "
        f"| {ca['mean_top_voi_per_cost']:.4f} | {ca['mean_random_voi_per_cost']:.4f} "
        f"| {ca['lift']:.4f} | {ca_ratio_str} |"
    )
    lines.append("")
    lines.append(
        f"**Raw lift = {lift['lift']:.4f}** (ratio {ratio_str}): in this substrate "
        "the blocking axes of a query are corpus-wide-⊥ and share the *same* "
        "two-world regret, so raw VoI does not by itself discriminate *which* ⊥ "
        "field to measure — the §8.7 regret is a property of the query's binding "
        "structure, not of the ⊥-axis label. "
        f"**Cost-aware lift = {ca['lift']:.4f}** (ratio {ca_ratio_str}): the "
        "cost-aware VoI/cost ranking *does* beat a random pick, because cheap axes "
        "(cost, latency) break the raw-VoI ties. That cost-aware signal is what "
        "drives `acquire_next` toward measurable cost first (the P5 preview)."
    )
    lines.append("")
    return "\n".join(lines)


def _print_summary(summary: dict, lift: dict) -> None:
    n = summary["n"]
    ar = summary["action_rates"]
    counts = summary["counts"]
    n_ab = summary["n_abstain"]

    print("=" * 72)
    print(
        f"P4 SELECTIVE-PROCEDURE EVAL  (provenance={PROVENANCE}, "
        f"regime={summary['regime']}, phi={PHI.value}, kappa={'+'.join(KAPPA)})"
    )
    print("=" * 72)
    print(f"Battery: {n} real deployment queries (ZenML empirical prior)")

    print("\nAction rates:")
    print(f"  COMMIT (coverage)   {counts['commit']:>5}  ({_fmt_pct(ar['commit'])})")
    print(f"  ABSTAIN             {counts['abstain']:>5}  ({_fmt_pct(ar['abstain'])})")
    print(
        f"  INFEASIBLE          {counts['infeasible']:>5}  "
        f"({_fmt_pct(ar['infeasible'])})"
    )

    print(f"\nAcquire-next distribution (over {n_ab} abstentions):")
    for axis, cnt in summary["acquire_next_distribution"].items():
        frac = _fmt_pct(cnt / n_ab) if n_ab else "-"
        print(f"  {axis:<18} {cnt:>5}  ({frac})")

    print(f"\nTop-blocking axis (highest RAW VoI, over {n_ab} abstentions):")
    for axis, cnt in summary["top_blocking_distribution"].items():
        frac = _fmt_pct(cnt / n_ab) if n_ab else "-"
        print(f"  {axis:<18} {cnt:>5}  ({frac})")

    print(
        f"\nMean top VoI = {summary['mean_top_voi']:.4f}  |  "
        f"mean VoI/cost (chosen) = {summary['mean_voi_per_cost']:.4f}"
    )

    print("\n" + "-" * 72)
    print(f"VoI LIFT (§10, seed={lift['seed']}, n={lift['n_abstain_with_ranking']}):")
    ratio = lift["lift_ratio"]
    ratio_str = f"{ratio:.2f}x" if ratio is not None else "n/a"
    print("  RAW VoI (field regret reduction):")
    print(f"    mean top-VoI axis    = {lift['mean_top_voi']:.4f}")
    print(f"    mean random-axis VoI = {lift['mean_random_voi']:.4f}")
    print(f"    lift                 = {lift['lift']:.4f}  (ratio {ratio_str})")
    ca = lift["cost_aware"]
    ca_ratio = ca["lift_ratio"]
    ca_ratio_str = f"{ca_ratio:.2f}x" if ca_ratio is not None else "n/a"
    print("  COST-AWARE VoI/cost (acquisition key):")
    print(f"    mean top axis        = {ca['mean_top_voi_per_cost']:.4f}")
    print(f"    mean random axis     = {ca['mean_random_voi_per_cost']:.4f}")
    print(f"    lift                 = {ca['lift']:.4f}  (ratio {ca_ratio_str})")
    print("=" * 72)


def main() -> None:
    # CachedSubstrate memoizes cell()/candidates() — the empirical battery issues
    # ~1716 queries over a fixed snapshot. C7 preserved.
    sub = CachedSubstrate(Substrate(DB_PATH))

    queries = build_empirical_queries(sub)
    evaluator = ProcedureEvaluator(
        sub, queries, kappa=KAPPA, phi=PHI, regime=FULL
    )
    summary = evaluator.run()
    lift = evaluator.voi_lift(seed=VOI_SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "regime": summary["regime"],
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "lam": summary["lam"],
            "voi_seed": VOI_SEED,
            "battery": "empirical-prior (ZenML)",
            "battery_n": summary["n"],
        },
        "summary": summary,
        "voi_lift": lift,
    }
    json_path = OUT_DIR / "procedure_eval.json"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8"
    )

    md_path = OUT_DIR / "procedure_eval.md"
    md_path.write_text(_render_md(summary, lift), encoding="utf-8")

    _print_summary(summary, lift)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
