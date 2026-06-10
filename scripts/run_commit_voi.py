"""Validate the POSITIVE COMMIT branch + scale VoI acquisition (W11 / C3).

Two C3 "positive-action" validations the V1 lattice never exercised:

  1. COMMIT-branch validity (``commit_validation``).  On every biting GT slice
     (the slices ``scale_v1`` masks), run the selective procedure under the FULL
     evidence regime — the binding axis IS observed — so it COMMITs, and score each
     commit against ground truth: ``feasible_frac`` (never commit a violation) and
     ``min_sufficient_frac`` (zero decision-regret vs the B5 oracle = the cheapest
     feasible config).  Each query is re-run masked to record the DUAL: the same
     slice forces ABSTAIN when the axis is hidden.  Closes the mock-review gap that
     selective coverage was 0 on every biting slice, so COMMIT was never scored.

  2. Scaled VoI acquisition (``scale_v2``).  Lifts the §10 VoI result from the n=5
     BFCL pilot to BFCL + every per-benchmark RouterBench slice, pooling per-query
     (VoI-pick-correct, random-correct) pairs into a McNemar one-sided binomial
     test — pooled and H-confidence-only (the RouterBench flagship).

Writes:
  - outputs/p5/commit_voi.json — full results + provenance (no wall-clock).
  - outputs/p5/commit_voi.md   — per-slice COMMIT-quality table + scaled-VoI
                                 significance block.

Every verdict reads the substrate ONLY through the solver/validation layer (C7);
the GT slice SCOREs, never tunes (C8).  Substrate wrapped in CachedSubstrate.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_commit_voi.py
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
PROVENANCE = "P5-commit-voi"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def _render_md(commit: dict, voi: dict) -> str:
    lines: list[str] = []
    lines.append("# P5 — COMMIT-branch validity + scaled VoI acquisition (W11 / C3)")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ: `{PHI.value}`,  κ: `{'+'.join(KAPPA)}`,  seed: `{SEED}`")
    lines.append("")

    # ---- COMMIT-branch validity ----
    lines.append("## 1. COMMIT-branch validity (closes W11)")
    lines.append("")
    lines.append(
        "On each biting slice the selective procedure is run under the FULL evidence "
        "regime so it COMMITs, and each commit is scored against ground truth. "
        "`feasible_frac` = fraction of commits truly satisfying the bound axes "
        "(must be 1.0 — the selective rule never commits a violation). "
        "`min_sufficient_frac` = fraction of feasible commits whose true cost equals "
        "the oracle min-cost feasible config (zero regret). `dual` = the same slice "
        "forces ABSTAIN under the masked regime (selective coverage 0 when blind)."
    )
    lines.append("")
    lines.append(
        "| slice | conf | n_q | n_commit | coverage | feasible_frac | "
        "min_suff_frac | mean_regret | dual(abstain/blind) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for key, block in commit["slices"].items():
        m, c = block["meta"], block["commit"]
        if not c:
            lines.append(
                f"| {key} | {m.get('confidence', '?')} | — | — | "
                f"skipped(n_cand={m.get('n_candidates')}) | — | — | — | — |"
            )
            continue
        dual = "YES" if c["dual_validated"] else f"{c['n_masked_abstain']}/{m['n_queries']}"
        lines.append(
            f"| {key} | {m['confidence']} | {m['n_queries']} | {c['n_commit']} | "
            f"{_fmt(c['coverage'])} | {_fmt(c['feasible_frac'])} | "
            f"{_fmt(c['min_sufficient_frac'])} | {_fmt(c['mean_regret'])} | {dual} |"
        )
    lines.append("")

    def _commit_pool(title: str, p: dict) -> None:
        lines.append(f"**{title}:** "
                     f"n_queries={p['n_queries']}, n_commit={p['n_commit']}, "
                     f"coverage={_fmt(p['coverage'])}, "
                     f"feasible_frac={_fmt(p['feasible_frac'])} "
                     f"({p['n_feasible']}/{p['n_commit']}), "
                     f"min_sufficient_frac={_fmt(p['min_sufficient_frac'])} "
                     f"({p['n_min_sufficient']}/{p['n_feasible']}), "
                     f"mean_regret={_fmt(p['mean_regret'])}, "
                     f"masked-abstains={p['n_masked_abstain']}.")
        lines.append("")

    _commit_pool("POOLED (all slices)", commit["pooled"])
    _commit_pool("POOLED — H-CONFIDENCE ONLY (RouterBench flagship)",
                 commit["pooled_h_only"])

    # ---- scaled VoI ----
    vm = voi["meta"]
    lines.append("## 2. Scaled VoI acquisition (§10) — VoI-pick vs random")
    lines.append("")
    lines.append(
        f"Slices: {vm['n_slices']} "
        f"({vm['n_slices_with_abstentions']} produced abstentions to acquire on). "
        f"Construction: `{vm['construction']}`. Per abstained query we 'measure' the "
        "procedure's top-VoI axis vs a seeded random axis and re-decide; "
        "`commit_correct` = the re-decision COMMITs a truly-feasible config."
    )
    lines.append("")
    lines.append(
        "| slice | conf | n_abstain | VoI-pick cc | random cc | McNemar b/c | "
        "binom p | significant |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for key, block in voi["slices"].items():
        m, a = block["meta"], block["acquisition"]
        if a.get("n", 0) == 0:
            lines.append(f"| {key} | {m.get('confidence', '?')} | 0 | — | — | — | — | — |")
            continue
        lines.append(
            f"| {key} | {m['confidence']} | {a['n']} | "
            f"{_fmt(a['topvoi_commit_correct_frac'])} | "
            f"{_fmt(a['random_commit_correct_frac'])} | "
            f"{a['mcnemar_b']}/{a['mcnemar_c']} | {a['binom_p_one_sided']:.2e} | "
            f"{'YES' if a['significant'] else 'no'} |"
        )
    lines.append("")

    def _voi_pool(title: str, p: dict) -> None:
        lines.append(
            f"**{title}:** n={p['n']}, "
            f"VoI-pick commit-correct={_fmt(p['topvoi_commit_correct_frac'])} "
            f"({p['topvoi_commit_correct']}/{p['n']}), "
            f"random={_fmt(p['random_commit_correct_frac'])} "
            f"({p['random_commit_correct']}/{p['n']}), "
            f"McNemar b/c={p['mcnemar_b']}/{p['mcnemar_c']}, "
            f"binom p={p['binom_p_one_sided']:.2e}, "
            f"significant={'YES' if p['significant'] else 'no'}.")
        lines.append("")

    _voi_pool("POOLED (all slices)", voi["pooled"])
    _voi_pool("POOLED — H-CONFIDENCE ONLY (RouterBench flagship)",
              voi["pooled_h_only"])
    return "\n".join(lines)


def _print_summary(commit: dict, voi: dict) -> None:
    print("=" * 76)
    print(f"COMMIT-branch validity + scaled VoI  (provenance={PROVENANCE}, "
          f"phi={PHI.value}, kappa={'+'.join(KAPPA)}, seed={SEED})")
    print("=" * 76)
    cp, cph = commit["pooled"], commit["pooled_h_only"]
    print("\n[1] COMMIT-branch validity (full evidence → COMMIT, scored vs GT):")
    for tag, p in (("ALL ", cp), ("H-only", cph)):
        print(f"  {tag}: n_commit={p['n_commit']:>4}  coverage={p['coverage']:.3f}  "
              f"feasible_frac={p['feasible_frac']:.3f}  "
              f"min_sufficient_frac={p['min_sufficient_frac']:.3f}  "
              f"mean_regret={p['mean_regret']:.4f}  "
              f"masked-abstains={p['n_masked_abstain']}")
    vp, vph = voi["pooled"], voi["pooled_h_only"]
    print("\n[2] Scaled VoI acquisition (VoI-pick vs random commit-correct):")
    for tag, p in (("ALL ", vp), ("H-only", vph)):
        print(f"  {tag}: n={p['n']:>4}  "
              f"VoI-pick={p['topvoi_commit_correct_frac']:.3f}  "
              f"random={p['random_commit_correct_frac']:.3f}  "
              f"McNemar b/c={p['mcnemar_b']}/{p['mcnemar_c']}  "
              f"p={p['binom_p_one_sided']:.2e}  "
              f"significant={'YES' if p['significant'] else 'no'}")
    print("=" * 76)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(sub, kappa=KAPPA, phi=PHI)

    commit = runner.commit_validation()
    voi = runner.scale_v2(seed=SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "seed": SEED,
        },
        "commit_validation": commit,
        "scale_v2": voi,
    }
    json_path = OUT_DIR / "commit_voi.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    md_path = OUT_DIR / "commit_voi.md"
    md_path.write_text(_render_md(commit, voi), encoding="utf-8")

    _print_summary(commit, voi)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
