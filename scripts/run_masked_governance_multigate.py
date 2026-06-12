"""Multi-gate governance harm validation — extends E11 to 3 independent categorical gates.

Motivation: E11 shows blind-commit harm on ONE categorical governance axis
(self-hostability). A reviewer might argue the result is an artifact of that specific
gate. Here we replicate the exact same procedure under TWO additional real-world
governance gates (EU data-residency, commercial fine-tuning rights) and show the
hidden-violation rate holds across ALL three, with min(HVR_G1, HVR_G2, HVR_G3) > 0.

Gates:
  G1 — self-hostable / data-sovereignty (SAME as E11 — baseline replication):
       open-weights = admissible (1), proprietary-API = 0.

  G2 — EU data-residency / GDPR:
       open-weights = 1 (self-hostable anywhere in EU);
       gpt-* = 1 (OpenAI has documented EU data residency for Enterprise since 2023);
       claude-* = 0 (Anthropic has no documented EU data centers as of 2024).

  G3 — commercial fine-tuning rights:
       Apache-2.0 models only = 1 (Mistral-7B, Mixtral-8x7B);
       Llama-2 community license (Meta approval >700M MAU) = 0;
       Yi license (commercial with restrictions) = 0;
       proprietary-API (no fine-tuning rights) = 0.

Procedure: identical to E11 — GovernanceTruthSubstrate injects per-gate admissibility
via a synthetic 'governance' cell; MASK it; let blind rules commit on visible
quality+cost; score against hidden admissibility truth.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_masked_governance_multigate.py
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
OUT_DIR = Path("outputs/p3")
PROVENANCE = "multigate-governance-categorical"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
QUALITY_PCTS = (10, 30, 50, 70, 90)
MIN_CFG = 6
MASK = "governance"

_RB_MODELS = ValidationRunner._ROUTERBENCH_MODELS
_Obs = namedtuple("_Obs", ["confidence", "value_num"])

# ─────────────────────────────────────────────────────────────────────────────
# Gate definitions
# ─────────────────────────────────────────────────────────────────────────────

# G1 — self-hostable / data-sovereignty (exact E11 replication)
_G1_PROPRIETARY = frozenset({
    "rb-claude-instant-v1", "rb-claude-v1", "rb-claude-v2",
    "rb-gpt-3-5-turbo-1106", "rb-gpt-4-1106-preview",
})
_G1_ADMISSIBLE = frozenset(_RB_MODELS) - _G1_PROPRIETARY  # open-weights

# G2 — EU data-residency / GDPR
#   admissible: open-weights (self-hostable in EU) + gpt-* (OpenAI EU Enterprise)
#   inadmissible: claude-* (no Anthropic EU data center as of 2024)
_G2_INADMISSIBLE = frozenset({
    "rb-claude-instant-v1", "rb-claude-v1", "rb-claude-v2",
})
_G2_ADMISSIBLE = frozenset(_RB_MODELS) - _G2_INADMISSIBLE

# G3 — commercial fine-tuning rights
#   admissible: Apache-2.0 models only (no commercial restrictions)
_G3_ADMISSIBLE = frozenset({
    "rb-mistralai-mistral-7b-chat",    # Mistral-7B-Instruct-v0.2 — Apache-2.0
    "rb-mistralai-mixtral-8x7b-chat",  # Mixtral-8x7B — Apache-2.0
})
_G3_INADMISSIBLE = frozenset(_RB_MODELS) - _G3_ADMISSIBLE

GATES: dict[str, dict] = {
    "G1_self_hostable": {
        "label": "G1 — self-hostable / data-sovereignty",
        "admissible": _G1_ADMISSIBLE,
        "inadmissible": _G1_PROPRIETARY,
        "note": (
            "open-weights=1 (self-hostable); proprietary-API=0. "
            "Exact E11 replication."
        ),
    },
    "G2_eu_data_residency": {
        "label": "G2 — EU data-residency / GDPR",
        "admissible": _G2_ADMISSIBLE,
        "inadmissible": _G2_INADMISSIBLE,
        "note": (
            "open-weights=1; gpt-*=1 (OpenAI EU Enterprise data residency 2023+); "
            "claude-*=0 (no Anthropic EU data center documented as of 2024)."
        ),
    },
    "G3_fine_tuning_rights": {
        "label": "G3 — commercial fine-tuning rights",
        "admissible": _G3_ADMISSIBLE,
        "inadmissible": _G3_INADMISSIBLE,
        "note": (
            "Apache-2.0 only=1 (Mistral-7B, Mixtral-8x7B); "
            "Llama-2 community / Yi / proprietary-API=0."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure (mirrors run_masked_governance.py exactly)
# ─────────────────────────────────────────────────────────────────────────────

def _model_of(cid: str) -> str | None:
    for m in sorted(_RB_MODELS, key=len, reverse=True):
        if cid.startswith(m + "-"):
            return m
    return None


class GovernanceTruthSubstrate:
    """Injects a per-gate synthetic binary admissibility axis.

    cell(x, 'governance') → [_Obs('H', 0|1)] from the supplied admissible set.
    All other axes delegate unchanged to the frozen substrate.
    """

    def __init__(self, sub, admissible: frozenset[str]) -> None:
        self._sub = sub
        self._admissible = admissible

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        if a == MASK:
            xid = x if isinstance(x, str) else getattr(x, "id", x)
            model = _model_of(str(xid))
            if model is None:
                return []
            val = 1.0 if model in self._admissible else 0.0
            return [_Obs("H", val)]
        return self._sub.cell(x, a)

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def _gov_queries(mp: MaskAndPredict, tau: str) -> list:
    """Build quality-floor + governance>=1 queries at each QUALITY_PCTS percentile."""
    qpct = mp.observed_percentiles(tau, "quality", list(QUALITY_PCTS))
    if not qpct:
        return []
    queries = []
    for p in QUALITY_PCTS:
        cons = [("quality", ">=", qpct[p]), (MASK, ">=", 1.0)]
        q = make_query(tau, cons, label=f"q@p{p}+gov>=1")
        queries.append((p, q))
    return queries


# ─────────────────────────────────────────────────────────────────────────────
# Per-gate runner (same logic as main() in run_masked_governance.py)
# ─────────────────────────────────────────────────────────────────────────────

def run_gate(
    base_sub,
    gate_name: str,
    gate_cfg: dict,
    benches: list[str],
    by_name: dict,
) -> dict:
    """Run blind-commit harm analysis for one gate.  Returns the gate result dict."""
    gov = GovernanceTruthSubstrate(base_sub, gate_cfg["admissible"])
    blind = ["B2_observed_pareto", "B3_imputation", "B6_cost_accuracy"]
    keys = blind + ["B5_oracle", "selective_strict", "selective_measured"]

    pooled = {k: [] for k in keys}
    by_pct: dict[int, dict] = {p: {"n_commit": 0, "n_violation": 0} for p in QUALITY_PCTS}
    n_slices = 0
    n_admissible_exists = 0

    for bench in benches:
        bsub = BenchmarkSubstrate(gov, bench)
        if len(bsub.candidates("routerbench")) < MIN_CFG:
            continue
        mp = MaskAndPredict(bsub, kappa=KAPPA, phi=PHI)
        pq = _gov_queries(mp, "routerbench")
        if not pq:
            continue
        n_slices += 1

        for p, q in pq:
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

            ores = mp.score_rule_per_query(by_name["B5_oracle"], [q], MASK)[0]
            pooled["B5_oracle"].append(ores)
            sres = mp.score_rule_per_query(by_name["selective"], [q], MASK)[0]
            pooled["selective_strict"].append(sres)
            pooled["selective_measured"].append(
                {"committed": ores["committed"], "hidden_violation": ores["hidden_violation"]}
            )

    def summarize(key):
        v = pooled[key]
        if not v:
            return {"n": 0, "n_committed": 0, "n_violations": 0, "coverage": 0.0, "hvr": 0.0}
        nc = sum(int(x["committed"]) for x in v)
        nv = sum(int(x["hidden_violation"]) for x in v)
        return {
            "n": len(v),
            "n_committed": nc,
            "n_violations": nv,
            "coverage": round(nc / len(v), 4) if v else 0.0,
            "hvr": round(nv / nc, 4) if nc else 0.0,
        }

    summary = {k: summarize(k) for k in keys}

    grading: dict[int, dict] = {}
    for p in QUALITY_PCTS:
        c = by_pct[p]
        grading[p] = {
            "n_commit": c["n_commit"],
            "n_violation": c["n_violation"],
            "hvr": round(c["n_violation"] / c["n_commit"], 4) if c["n_commit"] else 0.0,
        }

    return {
        "gate": gate_name,
        "label": gate_cfg["label"],
        "note": gate_cfg["note"],
        "n_slices": n_slices,
        "n_query_instances": len(pooled["B2_observed_pareto"]),
        "admissible_exists_instances": n_admissible_exists,
        "n_admissible_models": len(gate_cfg["admissible"]),
        "admissible_models": sorted(gate_cfg["admissible"]),
        "inadmissible_models": sorted(gate_cfg["inadmissible"]),
        "pooled": summary,
        "b2_hvr_by_quality_percentile": grading,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    base = CachedSubstrate(Substrate(DB_PATH))
    runner = ValidationRunner(base, kappa=KAPPA, phi=PHI)
    benches = runner.discover_routerbench_benchmarks()
    rng = random.Random(SEED)

    by_name = {r.name: r for r in ALL_RULES}

    gate_results: dict[str, dict] = {}
    for gate_name, gate_cfg in GATES.items():
        print(f"\n--- Running {gate_cfg['label']} ({len(gate_cfg['admissible'])} admissible models) ---")
        gate_results[gate_name] = run_gate(base, gate_name, gate_cfg, benches, by_name)
        b2_hvr = gate_results[gate_name]["pooled"]["B2_observed_pareto"]["hvr"]
        print(f"    B2 HVR = {100 * b2_hvr:.1f}%  (n_instances={gate_results[gate_name]['n_query_instances']})")

    # Cross-gate robustness: min HVR across all three gates
    hvr_values = {
        gn: gate_results[gn]["pooled"]["B2_observed_pareto"]["hvr"]
        for gn in GATES
    }
    min_hvr = min(hvr_values.values())
    max_hvr = max(hvr_values.values())
    bite_holds_all_gates = min_hvr > 0.0

    # ── JSON output ──────────────────────────────────────────────────────────
    res = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "seed": SEED,
            "mask": MASK,
            "quality_pcts": list(QUALITY_PCTS),
            "n_benchmarks": len(benches),
            "claim": (
                "blind-commit harm (B2 HVR > 0) is robust across all three independent "
                "categorical governance gates; min(HVR_G1, HVR_G2, HVR_G3) > 0 iff "
                "'bite_holds_all_gates' is true."
            ),
        },
        "cross_gate_summary": {
            "b2_hvr_per_gate": {gn: round(hvr_values[gn], 4) for gn in GATES},
            "min_hvr": round(min_hvr, 4),
            "max_hvr": round(max_hvr, 4),
            "bite_holds_all_gates": bite_holds_all_gates,
        },
        "gates": gate_results,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "multigate_governance.json"
    json_path.write_text(json.dumps(res, indent=2), encoding="utf-8")

    # ── Markdown output ──────────────────────────────────────────────────────
    lines = [
        "# Multi-gate governance harm validation",
        "",
        "Extends E11 (single self-hostability gate) to 3 independent categorical governance gates.",
        "If blind-commit harm is real — not an artifact of one gate choice — the hidden-violation",
        "rate (HVR) should be > 0 under ALL gates.",
        "",
        "## Cross-gate summary (B2 observed-Pareto blind rule)",
        "",
        "| gate | admissible models | B2 HVR | query instances |",
        "|---|---|---|---|",
    ]
    for gn, gcfg in GATES.items():
        gr = gate_results[gn]
        b2 = gr["pooled"]["B2_observed_pareto"]
        lines.append(
            f"| {gcfg['label']} | {gr['n_admissible_models']} | "
            f"**{100 * b2['hvr']:.1f}%** | {gr['n_query_instances']} |"
        )
    lines += [
        "",
        f"- **min HVR across all gates: {100 * min_hvr:.1f}%** — "
        f"bite_holds_all_gates = `{bite_holds_all_gates}`",
        "",
    ]

    for gn, gcfg in GATES.items():
        gr = gate_results[gn]
        b2 = gr["pooled"]["B2_observed_pareto"]
        lines += [
            f"## {gcfg['label']}",
            "",
            f"_{gcfg['note']}_",
            "",
            f"- {gr['n_slices']} benchmark slices, {gr['n_query_instances']} query instances",
            f"- admissible models ({gr['n_admissible_models']}): {', '.join(gr['admissible_models'])}",
            f"- inadmissible: {', '.join(gr['inadmissible_models'])}",
            "",
            "| rule | coverage | HVR | committed | violations |",
            "|---|---|---|---|---|",
        ]
        keys = [
            "B2_observed_pareto", "B3_imputation", "B6_cost_accuracy",
            "B5_oracle", "selective_strict", "selective_measured",
        ]
        for k in keys:
            s = gr["pooled"][k]
            lines.append(
                f"| {k} | {s['coverage']:.2f} | {s['hvr']:.4f} | "
                f"{s['n_committed']} | {s['n_violations']} |"
            )
        lines += [
            "",
            f"**B2 HVR = {100 * b2['hvr']:.1f}%** "
            f"({b2['n_violations']} hidden violations / {b2['n_committed']} commits)",
            "",
            "### B2 HVR by quality-floor percentile",
            "",
            "| quality pct | commit | violations | HVR |",
            "|---|---|---|---|",
        ]
        for p in QUALITY_PCTS:
            g = gr["b2_hvr_by_quality_percentile"][p]
            lines.append(
                f"| p{p} | {g['n_commit']} | {g['n_violation']} | "
                f"{100 * g['hvr']:.1f}% |"
            )
        lines.append("")

    md_path = OUT_DIR / "multigate_governance.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
