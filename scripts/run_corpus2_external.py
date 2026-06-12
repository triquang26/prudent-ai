"""External-validity replication on an INDEPENDENT second corpus (improvement 2).

Round-9 / improvement (2): every reviewer flags that the query prior comes from a
single corpus (the ZenML LLMOps DB), and that publication self-selection is the key
external-validity limitation. We address it with a genuinely independent second
corpus: the Evidently AI ML/LLM system-design database (MIT-licensed GitHub mirror
themanojdesai/genai-llm-ml-case-studies, commit pinned in data/corpus2_evidently/
SOURCE.txt), separately curated from engineering blogs since 2023 -- a different
maintainer and selection method than ZenML.

Like ZenML, it records industry + application use-case per deployment but NOT explicit
constraints (those are always derived). We apply the SAME derivation SEMANTICS as
corpus 1 -- universal quality, an industry governance rule for regulated sectors, and
a use-case->axis map mirroring corpus 1's tag->axis rules -- then run the IDENTICAL
decidability classifier against the SAME frozen substrate. The test: does the
underdetermination headline and its governance/reviewer-burden blind-spot structure
REPLICATE on an independently-collected corpus?

The use-case->axis mapping across the two tag vocabularies is necessarily approximate
and is documented below (C2_TAG_TO_AXIS); we report the result honestly whichever way
it falls. Corpus 2 is more consumer-tech-skewed (e-commerce/delivery/social) with
fewer regulated-industry deployments than ZenML, so if the blind spot survives here it
is a conservative replication.

Frozen db read-only via the immutable interface; nothing imputed; no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_corpus2_external.py
"""

from __future__ import annotations

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
CORPUS2 = Path("data/corpus2_evidently/case-studies/by-industry")
OUT_DIR = Path("outputs/p3")
PROVENANCE = "external-corpus2-evidently"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

# Regulated industries (governance binds), mirroring corpus 1's REGULATED_INDUSTRIES.
# Corpus 2 industry strings come from the by-industry/ filenames + table context.
REGULATED_SUBSTR = ("fintech", "banking", "finance", "health", "insurance", "legal")

# Use-case tag -> binding axis, mirroring corpus 1's TAG_TO_AXIS SEMANTICS across the
# two (different) tag vocabularies. Documented and deliberately conservative.
C2_TAG_TO_AXIS: dict[str, str] = {
    # high-stakes / moderation -> governance (= corpus 1 fraud_detection,
    # content_moderation, high_stakes_application)
    "fraud detection": "governance",
    "spam / content moderation": "governance",
    "spam/content moderation": "governance",
    # human-facing assistive use cases -> reviewer_burden (human-in-the-loop review)
    "customer support": "reviewer_burden",
    "chatbot": "reviewer_burden",
    "voice interface": "reviewer_burden",
    # interactive serving -> latency
    "search": "latency_p95",
    "recommender system": "latency_p95",
    "recommender systems": "latency_p95",
    "ad ranking / targeting": "latency_p95",
    "ad ranking/targeting": "latency_p95",
    "eta prediction": "latency_p95",
}

# Use-case tag -> application archetype (tau), mirroring corpus 1's ARCHETYPE_MAP so
# the substrate's per-tau cost coverage applies the SAME way (else forcing one tau
# would make cost universally block). Serving > structured > general-qa default.
C2_SERVING = {"search", "recommender system", "recommender systems",
              "ad ranking / targeting", "ad ranking/targeting", "eta prediction",
              "demand forecasting", "pricing", "propensity to buy", "lead scoring",
              "churn prediction", "predictive maintenance"}
C2_STRUCTURED = {"item classification", "item classificatiion", "fraud detection",
                 "spam / content moderation", "spam/content moderation"}

_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*(\d{4})\s*\|\s*(.*?)\s*\|\s*$")
_TAG = re.compile(r"`([^`]+)`")


def tau_of(tags: list[str]) -> str:
    if any(t in C2_SERVING for t in tags):
        return "inference-serving"
    if any(t in C2_STRUCTURED for t in tags):
        return "function-calling"
    return DEFAULT_TAU  # general-qa


def parse_corpus2() -> list[dict]:
    rows: list[dict] = []
    for md in sorted(CORPUS2.glob("*.md")):
        industry = md.stem.replace("-", " ")
        for line in md.read_text(encoding="utf-8").splitlines():
            m = _ROW.match(line)
            if not m:
                continue
            company = m.group(1).strip()
            if company.lower() in ("company", "---------"):
                continue
            title = m.group(2)
            tags = [t.strip().lower() for t in _TAG.findall(m.group(4))]
            rows.append({"company": company, "industry": industry,
                         "title": re.sub(r"\[|\]\(.*", "", title)[:80], "tags": tags})
    return rows


def derive_c2(row: dict) -> DerivedQuery:
    """Same derivation semantics as corpus 1: universal quality, an industry
    governance rule, and the use-case->axis map (C2_TAG_TO_AXIS)."""
    axes = set(UNIVERSAL_AXES)  # quality always binds
    ind = row["industry"].lower()
    if any(s in ind for s in REGULATED_SUBSTR):
        axes.add("governance")
    for t in row["tags"]:
        ax = C2_TAG_TO_AXIS.get(t)
        if ax:
            axes.add(ax)
    return DerivedQuery(tau=tau_of(row["tags"]), binding_axes=frozenset(axes),
                        title=row["title"], industry=row["industry"])


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows = parse_corpus2()
    derived = [derive_c2(r) for r in rows]
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
                     "kappa": list(KAPPA), "n_deployments": n,
                     "source": "Evidently AI / themanojdesai mirror (MIT), see "
                               "data/corpus2_evidently/SOURCE.txt",
                     "note": "INDEPENDENT corpus, same frozen substrate + same "
                             "derivation semantics + same classifier. Compare to "
                             "corpus-1 headline 91.1% / blind-spot 72.4%."},
        "n": n,
        "underdetermined": n_und,
        "frac_underdetermined": fr(n_und),
        "blindspot_attributable": n_blindspot,
        "frac_blindspot": fr(n_blindspot),
        "axis_demand_rate": {a: fr(demand[a]) for a in AXES},
        "blockers": dict(sorted(blocker_tally.items(), key=lambda kv: -kv[1])),
        "modal_blocker": modal,
        "corpus1_reference": {"frac_underdetermined": 0.911, "frac_blindspot": 0.724},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "corpus2_external.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = [
        "# External-validity replication on an independent second corpus (Evidently AI)",
        "",
        f"- corpus 2: **{n}** independently-curated deployments (MIT mirror; "
        f"different maintainer/selection than ZenML)",
        f"- **underdetermined: {n_und}/{n} = {100 * fr(n_und):.1f}%** "
        f"(corpus 1: 91.1%)",
        f"- **blind-spot-attributable: {100 * fr(n_blindspot):.1f}%** "
        f"(corpus 1: 72.4%)",
        f"- modal blocker: **{modal}**",
        "",
        "## axis demand rate (fraction of corpus-2 deployments declaring the axis)",
        "",
        "| axis | demand rate |",
        "|---|---|",
    ]
    for a in AXES:
        lines.append(f"| {a} | {100 * fr(demand[a]):.1f}% |")
    lines += ["", "## blockers among underdetermined", "",
              "| axis | count |", "|---|---|"]
    for a, c in res["blockers"].items():
        lines.append(f"| {a} | {c} |")
    (OUT_DIR / "corpus2_external.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'corpus2_external.json'} and .md")


if __name__ == "__main__":
    main()
