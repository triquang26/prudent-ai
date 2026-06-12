"""External-validity replication on a THIRD independent corpus (improvement 2, cont.).

Corpus 3: the US Federal AI Use Case Inventory (OMB), 2025 edition. Genuinely
independent of both ZenML (corpus 1) and Evidently AI (corpus 2): a different curator
(US OMB), a different selection method (legally-mandated agency self-reporting under
EO 13960 / M-24-10), public domain (17 USC 105). Source pinned in
data/corpus3_omb/SOURCE.txt.

This corpus is US PUBLIC-SECTOR (the opposite skew of corpus 2's consumer tech), so it
brackets the governance-attribution question: if corpus 2 (tech, low governance demand)
and corpus 3 (government, high governance demand) BOTH replicate the headline, the
finding is robust across maximally different deployment populations, with the blind-spot
share scaling with governance demand exactly as the mechanism predicts.

We filter to the GenAI/LLM-relevant subset (keyword scan), derive queries under the SAME
semantics as corpora 1-2 (universal quality; governance for high-stakes domains and
rights/safety-impacting systems; reviewer burden for human-facing/oversight use cases;
latency for interactive serving), and run the IDENTICAL classifier against the SAME
frozen substrate. The domain->axis mapping is documented and conservative.

Frozen db read-only via the immutable interface; nothing imputed; no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_corpus3_omb.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
)
from prudent_ai.queries.query_prior import (
    DEFAULT_TAU,
    UNIVERSAL_AXES,
    DerivedQuery,
    to_query,
)
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
CSV_PATH = Path("data/corpus3_omb/omb2025.csv")
OUT_DIR = Path("outputs/p3")
PROVENANCE = "external-corpus3-omb-federal"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

# GenAI/LLM relevance filter (same spirit as the LLM tags in corpora 1-2).
_GEN = re.compile(
    r"gener|llm|gpt|chatbot|\brag\b|summar|language model|copilot|conversational|"
    r"natural language|\bnlp\b|text generation|claude|prompt", re.I)

# High-stakes / regulated topic areas -> governance binds (mirrors corpus 1's
# REGULATED_INDUSTRIES + high_stakes_application semantics).
_GOV_TOPICS = {"health and medical", "law enforcement", "benefits processing",
               "cybersecurity", "procurement and finance mgmt", "emergency mgmt",
               "diplomacy and trade", "law and justice"}
# Human-facing / oversight use cases -> reviewer burden (mirrors corpus 2's
# chatbot/customer-support/voice -> reviewer_burden).
_REV = re.compile(r"chatbot|assistant|copilot|conversational|draft|triage|review|"
                  r"summar|question answer|\bq&a\b|help desk|customer", re.I)
# Interactive serving -> latency (mirrors corpus 2's search/recommender -> latency).
_LAT = re.compile(r"search|retrieval|real[- ]?time|recommend|routing|detection|"
                  r"monitoring", re.I)


def _text(r: dict) -> str:
    return " ".join((r.get(k) or "") for k in
                    ("use_case_name", "problem_solved", "benefits", "system_outputs"))


def tau_of(text: str) -> str:
    if _LAT.search(text):
        return "inference-serving"
    if re.search(r"classif|extract|structured|tagging|categor", text, re.I):
        return "function-calling"
    return DEFAULT_TAU


def derive_omb(r: dict) -> DerivedQuery:
    """Same derivation semantics as corpora 1-2, applied to OMB fields."""
    text = _text(r)
    axes = set(UNIVERSAL_AXES)  # quality always binds
    topic = (r.get("topic_area") or "").strip().lower()
    high_impact = (r.get("is_high_impact") or "").strip().lower() == "high-impact"
    has_pii = (r.get("has_pii") or "").strip().lower() == "yes"
    # governance: high-stakes domain, or a rights/safety-impacting system, or PII
    if topic in _GOV_TOPICS or high_impact or has_pii:
        axes.add("governance")
    if _REV.search(text):
        axes.add("reviewer_burden")
    if _LAT.search(text):
        axes.add("latency_p95")
    return DerivedQuery(tau=tau_of(text), binding_axes=frozenset(axes),
                        title=(r.get("use_case_name") or "")[:80],
                        industry=(r.get("topic_area") or "").strip())


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig")))
    gen = [r for r in rows if _GEN.search(_text(r))]
    derived = [derive_omb(r) for r in gen]
    taus = sorted({d.tau for d in derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    n = len(derived)
    n_und = 0
    n_blindspot = 0
    demand: dict[str, int] = dict.fromkeys(AXES, 0)
    blocker_tally: dict[str, int] = {}
    for dq in derived:
        for a in dq.binding_axes:
            demand[a] = demand.get(a, 0) + 1
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1
        b = set(res.blocking_axes)
        for a in b:
            blocker_tally[a] = blocker_tally.get(a, 0) + 1
        if b & UNMEASURABLE_AXES:
            n_blindspot += 1

    def fr(x):
        return round(x / n, 4) if n else 0.0

    modal = max(blocker_tally, key=blocker_tally.get) if blocker_tally else None
    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
                     "kappa": list(KAPPA), "n_total_rows": len(rows),
                     "n_genai_deployments": n,
                     "source": "US Federal AI Use Case Inventory 2025 (OMB), public "
                               "domain; see data/corpus3_omb/SOURCE.txt",
                     "note": "INDEPENDENT US public-sector corpus; same frozen "
                             "substrate + same derivation semantics + same classifier. "
                             "Compare to corpus-1 (91.1%/72.4%) and corpus-2 "
                             "(96.4%/17.5%)."},
        "n": n,
        "underdetermined": n_und,
        "frac_underdetermined": fr(n_und),
        "blindspot_attributable": n_blindspot,
        "frac_blindspot": fr(n_blindspot),
        "axis_demand_rate": {a: fr(demand[a]) for a in AXES},
        "blockers": dict(sorted(blocker_tally.items(), key=lambda kv: -kv[1])),
        "modal_blocker": modal,
        "corpus1_reference": {"frac_underdetermined": 0.911, "frac_blindspot": 0.724},
        "corpus2_reference": {"frac_underdetermined": 0.964, "frac_blindspot": 0.175},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "corpus3_omb.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = [
        "# External-validity replication on a third independent corpus (US Federal AI Inventory)",
        "",
        f"- corpus 3: **{n}** GenAI/LLM deployments (of {len(rows)} total AI use cases; "
        f"US public-sector, OMB, public domain)",
        f"- **underdetermined: {n_und}/{n} = {100 * fr(n_und):.1f}%** "
        f"(corpus 1: 91.1%, corpus 2: 96.4%)",
        f"- **blind-spot-attributable: {100 * fr(n_blindspot):.1f}%** "
        f"(corpus 1: 72.4%, corpus 2: 17.5%)",
        f"- modal blocker: **{modal}**",
        "",
        "## axis demand rate (fraction of corpus-3 deployments declaring the axis)",
        "",
        "| axis | demand rate |",
        "|---|---|",
    ]
    for a in AXES:
        lines.append(f"| {a} | {100 * fr(demand[a]):.1f}% |")
    lines += ["", "## blockers among underdetermined", "", "| axis | count |", "|---|---|"]
    for a, c in res["blockers"].items():
        lines.append(f"| {a} | {c} |")
    (OUT_DIR / "corpus3_omb.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'corpus3_omb.json'} and .md")


if __name__ == "__main__":
    main()
