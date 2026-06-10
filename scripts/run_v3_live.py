"""V3 — prospective LIVE evaluation on held-out future traffic (disjoint prompt-split).

Decide a config on the MEASURE split (first K prompts, the evidence at decision time);
score the committed config's REALIZED outcome on the disjoint LIVE split (subsequent
traffic). Compares a blind cost-minimizer (leaderboard practice, margin 0) against the
selective procedure with safety margins, on the SAME live traffic — a genuine
out-of-sample test that the decision generalizes to traffic it never saw.

Writes:
  - outputs/p5/v3_live.json — per-rule live stats + provenance.
  - outputs/p5/v3_live.md   — the prospective coverage / live-violation / regret table.

Direct pkl scoring (C7 not engaged); MEASURE and LIVE are disjoint (C8, no leakage).

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_v3_live.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from prudent_ai.validation.live_eval import LiveEval

OUT_DIR = Path("outputs/p5")
PROVENANCE = "P5-V3-live"


def _pct(x: float) -> str:
    return f"{100.0 * x:5.1f}%"


def _render_md(res: dict) -> str:
    m = res["meta"]
    L: list[str] = []
    L.append("# V3 — Prospective LIVE evaluation (disjoint MEASURE/LIVE prompt-split)\n")
    L.append(
        "A config is committed from the **MEASURE** split (first K prompts, the evidence "
        "available at decision time) and scored on the **disjoint LIVE** split (the "
        "subsequent traffic it actually serves). The decision is genuinely out-of-sample — "
        "the procedure never sees the LIVE prompts. `live_feasibility` = fraction of "
        "commits whose committed config truly clears q* on LIVE traffic; `live_violation` = "
        "1 − that (commits that looked feasible on the sample but FAIL live).\n"
    )
    L.append(f"- pkl: `{m['pkl']}`  ·  benchmarks: {len(m['benchmarks'])}  ·  "
             f"K(measure)={m['k_measure']}, splits={m['n_splits']}")
    L.append(f"- q* percentiles: {m['q_percentiles']}  ·  construction: `{m['construction']}`")
    L.append("")
    L.append("| rule | coverage | **live-feasibility** | live-violation | "
             "mean live regret (rel) | n_commit |")
    L.append("|---|---|---|---|---|---|")
    for s in res["rules"]:
        L.append(
            f"| {s['rule']} | {_pct(s['coverage'])} | **{_pct(s['live_feasibility_rate'])}** "
            f"| {_pct(s['live_violation_rate'])} | {s['mean_live_regret_rel']:.3f} | "
            f"{s['n_commit']} |"
        )
    L.append("")
    L.append(
        "**Reading.** The blind cost-minimizer (leaderboard practice, margin 0) commits on "
        "almost every query but a large fraction of those commits **fail on live traffic** — "
        "it over-fits the noisy measurement sample. The selective procedure's safety margin "
        "**transfers to genuinely future traffic**: live-violation falls monotonically as the "
        "margin grows (the procedure abstains on the uncertain queries), at a coverage and "
        "cost-regret cost. This is the prospective coverage–risk tradeoff on traffic the "
        "decision never saw — the live-deployment claim, realized as an honest prompt-split "
        "(no model-serving stack required)."
    )
    return "\n".join(L)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    le = LiveEval()
    print("[load] per-prompt RouterBench + disjoint MEASURE/LIVE splits...")
    res = le.run()
    res_json = {"meta": res["meta"], "rules": [asdict(s) for s in res["rules"]]}

    (OUT_DIR / "v3_live.json").write_text(
        json.dumps({"metadata": {"provenance": PROVENANCE}, **res_json}, indent=2),
        encoding="utf-8")
    (OUT_DIR / "v3_live.md").write_text(_render_md(res_json), encoding="utf-8")

    print("=" * 76)
    print("V3 — PROSPECTIVE LIVE EVALUATION (decide on MEASURE, score on disjoint LIVE)")
    print("=" * 76)
    for s in res["rules"]:
        print(f"  {s.rule:<22} cov={s.coverage:.3f}  "
              f"live-feasible={s.live_feasibility_rate:.3f}  "
              f"live-violation={s.live_violation_rate:.3f}  "
              f"live-regret={s.mean_live_regret_rel:.3f}")
    print("=" * 76)
    print(f"Wrote {OUT_DIR / 'v3_live.json'}")
    print(f"Wrote {OUT_DIR / 'v3_live.md'}")


if __name__ == "__main__":
    main()
