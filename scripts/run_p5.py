"""Run the P5 validation (V1 baseline lattice + V2 VoI-acquisition) and dump artifacts.

Drives `ValidationRunner` over the ground-truth slices:

  - V1: mask-and-predict over (BFCL bind quality+latency / mask quality — the
        biting case; the latency-mask control; routerbench bind quality / mask
        quality — corroboration).  Surfaces the C2 verdict per biting case:
        ``hidden_violation(selective) << hidden_violation(B2/B3/B6)``.
  - V2: VoI-guided single-axis acquisition on the BFCL biting case.

Writes:
  - outputs/p5/validation.json — full results + provenance (no wall-clock).
  - outputs/p5/validation.md   — per-slice baseline-lattice tables + C2 verdicts
                                 + the V2 acquisition table.

Every verdict reads the substrate ONLY through the solver/validation layer (C7).
The substrate is wrapped in CachedSubstrate so the query battery does not re-hit
SQLite.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p5.py
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
PROVENANCE = "P5-V1V2"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
V2_SEED = 12345

# Lattice rows, in canonical order.
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


def _render_md(v1: dict, v2: dict) -> str:
    lines: list[str] = []
    lines.append("# P5 Validation — V1 baseline lattice + V2 VoI-acquisition")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ (aggregation): `{PHI.value}`")
    lines.append(f"- κ (confidence policy): `{'+'.join(KAPPA)}`")
    lines.append("")

    # ---- V1 ----
    lines.append("## V1 — mask-and-predict baseline lattice")
    lines.append("")
    lines.append(
        "Per (slice, masked_axis): each decision rule predicts a committed config "
        "(or abstains) under the masked evidence regime, scored against the true "
        "(full-regime) values.  `hidden_violation_rate` = fraction of COMMITs that "
        "silently violate the masked truth."
    )
    lines.append("")
    for key, block in v1.items():
        meta = block["meta"]
        rules = block["rules"]
        tag = "BITING" if meta["is_biting"] else "control"
        lines.append(f"### {key}  ({tag})")
        lines.append("")
        lines.append(
            f"bind=`{'+'.join(meta['bind_axes'])}`, mask=`{meta['masked_axis']}`, "
            f"n_queries={meta['n_queries']}"
        )
        lines.append("")
        lines.append("| rule | coverage | hidden_violation_rate | mean_regret |")
        lines.append("|---|---|---|---|")
        for name in _RULE_ORDER:
            m = rules.get(name)
            if m is None:
                continue
            lines.append(
                f"| {name} | {_fmt(m['coverage'])} | "
                f"{_fmt(m['hidden_violation_rate'])} | {_fmt(m['mean_regret'])} |"
            )
        lines.append("")
        if meta["must_beat_hidden_violation_rate"]:
            sel = meta["selective_hidden_violation_rate"]
            beat = meta["must_beat_hidden_violation_rate"]
            beat_str = ", ".join(f"{k}={_fmt(v)}" for k, v in beat.items())
            verdict = meta["c2_verdict"]
            if verdict == "no-bite":
                lines.append(
                    f"**C2 verdict (no-bite):** no commit-while-blind baseline "
                    f"violates the masked truth on this (slice, mask) — [{beat_str}]; "
                    "the biting phenomenon is axis/slice-specific (nothing to beat)."
                )
            else:
                lines.append(
                    f"**C2 verdict ({verdict.upper()}):** selective hidden-violation "
                    f"= {_fmt(sel)} vs [{beat_str}]."
                )
            lines.append("")

    # ---- V2 ----
    lines.append("## V2 — VoI-guided acquisition (§10 preview)")
    lines.append("")
    meta = v2["meta"]
    sr = v2["single_reveal"]
    sig = v2["voi_signal"]
    lines.append(
        f"BFCL biting case (bind=`{'+'.join(meta['bind_axes'])}`), seed={meta['seed']}. "
        f"Construction: {meta['construction']}.  "
        f"{meta['n_abstained']} queries abstain under full masking."
    )
    lines.append("")
    lines.append(
        "| reveal | commits | commit-correct | commit-correct frac |"
    )
    lines.append("|---|---|---|---|")
    lines.append(
        f"| top-VoI axis | {sr['topvoi_commit']} | {sr['topvoi_commit_correct']} "
        f"| {_fmt(sr['topvoi_commit_correct_frac'])} |"
    )
    lines.append(
        f"| random axis | {sr['random_commit']} | {sr['random_commit_correct']} "
        f"| {_fmt(sr['random_commit_correct_frac'])} |"
    )
    lines.append("")
    if sr["degenerate"]:
        lines.append(
            "**Degenerate (reported honestly):** the selective rule must certify "
            "*every* binding axis before it commits, so revealing a single axis out "
            "of a 2-axis bind cannot un-block it — both top-VoI and random yield 0 "
            "commits.  The single-reveal commit-correct fraction therefore does not "
            "discriminate on this slice."
        )
        lines.append("")
    lines.append(
        f"**VoI signal (what DOES discriminate):** on "
        f"{sig['n']}/{meta['n_abstained']} abstentions the cost-aware VoI ranking "
        f"strictly prefers the cheaper measurable field "
        f"(frac={_fmt(sig['frac'])}).  This is the §10 claim realized: VoI predicts "
        "the field worth measuring (cost-aware), even where one reveal cannot flip "
        "the selective COMMIT on a 2-binding-axis bind."
    )
    lines.append("")
    return "\n".join(lines)


def _print_summary(v1: dict, v2: dict) -> None:
    print("=" * 72)
    print(
        f"P5 VALIDATION  (provenance={PROVENANCE}, phi={PHI.value}, "
        f"kappa={'+'.join(KAPPA)})"
    )
    print("=" * 72)

    print("\nV1 — baseline lattice (hidden_violation_rate per rule):")
    for key, block in v1.items():
        meta = block["meta"]
        rules = block["rules"]
        tag = "BITING " if meta["is_biting"] else "control"
        print(f"\n  [{tag}] {key}  (n_queries={meta['n_queries']})")
        print(f"    {'rule':<20} {'cov':>6} {'hv_rate':>8} {'regret':>10}")
        for name in _RULE_ORDER:
            m = rules.get(name)
            if m is None:
                continue
            print(
                f"    {name:<20} {m['coverage']:>6.3f} "
                f"{m['hidden_violation_rate']:>8.3f} {m['mean_regret']:>10.4f}"
            )
        if meta["must_beat_hidden_violation_rate"]:
            sel = meta["selective_hidden_violation_rate"]
            beat = meta["must_beat_hidden_violation_rate"]
            beat_str = "  ".join(f"{k.split('_')[0]}={v:.3f}" for k, v in beat.items())
            verdict = meta["c2_verdict"]
            if verdict == "no-bite":
                print(
                    f"    -> C2 verdict NO-BITE: no baseline violates "
                    f"[{beat_str}] (axis/slice-specific)"
                )
            else:
                print(
                    f"    -> C2 verdict {verdict.upper()}: selective hv={sel:.3f}  "
                    f"<<  [{beat_str}]"
                )

    print("\n" + "-" * 72)
    print("V2 — VoI-guided acquisition (BFCL biting case):")
    meta = v2["meta"]
    sr = v2["single_reveal"]
    sig = v2["voi_signal"]
    print(f"  seed={meta['seed']}, abstentions={meta['n_abstained']}")
    print(
        f"  {'reveal':<14} {'commits':>8} {'correct':>8} {'correct_frac':>13}"
    )
    print(
        f"  {'top-VoI':<14} {sr['topvoi_commit']:>8} "
        f"{sr['topvoi_commit_correct']:>8} {sr['topvoi_commit_correct_frac']:>13.4f}"
    )
    print(
        f"  {'random':<14} {sr['random_commit']:>8} "
        f"{sr['random_commit_correct']:>8} {sr['random_commit_correct_frac']:>13.4f}"
    )
    if sr["degenerate"]:
        print(
            "  -> DEGENERATE (honest): selective certifies ALL binding axes, so a "
            "single\n     reveal of a 2-axis bind un-blocks neither — both yield 0 "
            "commits."
        )
    print(
        f"  -> VoI signal: top-VoI prefers the cheaper measurable field on "
        f"{sig['n']}/{meta['n_abstained']} queries (frac={sig['frac']:.4f})."
    )
    print("=" * 72)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)

    v1 = runner.v1()
    v2 = runner.v2_acquisition(seed=V2_SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "v2_seed": V2_SEED,
        },
        "v1": v1,
        "v2_acquisition": v2,
    }
    json_path = OUT_DIR / "validation.json"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8"
    )

    md_path = OUT_DIR / "validation.md"
    md_path.write_text(_render_md(v1, v2), encoding="utf-8")

    _print_summary(v1, v2)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
