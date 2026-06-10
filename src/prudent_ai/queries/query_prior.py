"""Empirical query prior from the ZenML LLMOps Database — closes P3 open gate Q2.

P3's decidability map was computed over a hand-built query grid (honest caveat:
the headline "% underdetermined" was conditional on that grid, not on real
deployment traffic). This module derives an **empirical** distribution over
queries `q = (τ, c)` from 1716 real LLM-deployment case studies, so the
decidability headline becomes a claim about real traffic (C8: justified, not
cherry-picked).

The C8-critical artifact is the **tag → binding-axis taxonomy** below. Every
mapping is conservative and documented; axes we cannot read cleanly from the tags
(throughput, energy) are deliberately left UNBOUND rather than fabricated (C1).
Robustness to the taxonomy is reported by drop-one-tag sensitivity
(`mapping_sensitivity`), so no single mapping choice carries the finding.

Pipeline:
  ZenML rows --(derive_query)--> DerivedQuery(τ, binding-axes)
            --(grounded thresholds)--> Query(τ, bundle)
  The multiset of derived queries IS the empirical prior; classifying each one and
  tallying labels gives the real-traffic decidability profile.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from prudent_ai.solver.query import Query, make_query

# ---------------------------------------------------------------------------
# C8 ARTIFACT 1 — tag → binding right-sizing axis
# ---------------------------------------------------------------------------
# A tag binds an axis iff the deployment, by carrying that tag, declares a hard
# requirement on that axis. Conservative: only tags with unambiguous axis
# semantics appear. Tags present in either application_tags or techniques_tags
# are matched.
#
# Rationale per axis:
#   latency_p95     — explicit latency engineering or real-time SLO.
#   cost            — explicit cost/token-budget engineering.
#   governance      — regulated / high-stakes / safety-gating workloads.
#   reviewer_burden — a human is in the decision loop (review cost is a constraint).
#   memory_hw       — on-device / edge deployment (hardware-memory bound).
# Axes intentionally NOT mapped from tags (left ⊥-able, never fabricated, C1):
#   throughput, energy — no ZenML tag signals these cleanly.
TAG_TO_AXIS: dict[str, str] = {
    # latency_p95
    "latency_optimization": "latency_p95",
    "realtime_application": "latency_p95",
    # cost
    "cost_optimization": "cost",
    "token_optimization": "cost",
    # governance (safety / regulatory / high-stakes gating)
    "regulatory_compliance": "governance",
    "high_stakes_application": "governance",
    "content_moderation": "governance",
    "fraud_detection": "governance",
    # reviewer_burden
    "human_in_the_loop": "reviewer_burden",
    # memory_hw (edge / on-device)
    "internet_of_things": "memory_hw",
}

# ---------------------------------------------------------------------------
# C8 ARTIFACT 2 — regulated industries also bind governance
# ---------------------------------------------------------------------------
# Deployments in these sectors carry statutory obligations (HIPAA, SOX, GDPR,
# GLBA, etc.) that bind a governance constraint regardless of technique tags.
REGULATED_INDUSTRIES: frozenset[str] = frozenset({
    "Healthcare",
    "Finance",
    "Legal",
    "Insurance",
    "Government",
})

# ---------------------------------------------------------------------------
# C8 ARTIFACT 3 — application archetype → substrate τ
# ---------------------------------------------------------------------------
# The substrate is organized by EVIDENCE-source archetype (function-calling=BFCL,
# general-qa=HELM, inference-serving=MLPerf/ML.ENERGY); ZenML is organized by
# DEPLOYMENT-application archetype. We map the latter to the former coarsely. This
# mismatch is itself a finding (real deployment archetypes do not align with how
# the evidence corpus is sliced); the decidability result is nonetheless robust to
# it because governance/reviewer_burden/energy are ⊥ in EVERY τ.
ARCHETYPE_MAP: dict[str, str] = {
    # tool-use / structured / code → function-calling (BFCL-like)
    "code_generation": "function-calling",
    "code_interpretation": "function-calling",
    "structured_output": "function-calling",
    "data_integration": "function-calling",
    # serving-latency-dominated → inference-serving (MLPerf/ML.ENERGY-like)
    "realtime_application": "inference-serving",
    "speech_recognition": "inference-serving",
    # everything QA-ish → general-qa (HELM-like)
    "chatbot": "general-qa",
    "question_answering": "general-qa",
    "customer_support": "general-qa",
    "summarization": "general-qa",
    "translation": "general-qa",
    "classification": "general-qa",
    "content_moderation": "general-qa",
    "document_processing": "general-qa",
    "data_analysis": "general-qa",
}
DEFAULT_TAU = "general-qa"

# Quality always binds: every deployment carries an implicit quality floor.
UNIVERSAL_AXES: frozenset[str] = frozenset({"quality"})


@dataclass(frozen=True)
class DerivedQuery:
    """One deployment case mapped to (τ, binding-axes). weight = 1 per case."""

    tau: str
    binding_axes: frozenset[str]
    title: str = ""
    industry: str = ""


def _tags(row: dict, field_name: str) -> list[str]:
    return [t.strip() for t in (row.get(field_name) or "").split(",") if t.strip()]


def derive_query(row: dict, drop_tag: str | None = None) -> DerivedQuery:
    """Map one ZenML row → DerivedQuery via the documented taxonomy.

    Args:
        row: a ZenML dataset row.
        drop_tag: if set, that tag is ignored in TAG_TO_AXIS (for mapping
            sensitivity / drop-one robustness).
    """
    app = _tags(row, "application_tags")
    tech = _tags(row, "techniques_tags")
    all_tags = set(app) | set(tech)

    # archetype: first application tag that has a mapping, else default
    tau = DEFAULT_TAU
    for t in app:
        if t in ARCHETYPE_MAP:
            tau = ARCHETYPE_MAP[t]
            break

    axes: set[str] = set(UNIVERSAL_AXES)
    for t in all_tags:
        if t == drop_tag:
            continue
        if t in TAG_TO_AXIS:
            axes.add(TAG_TO_AXIS[t])

    industry = (row.get("industry") or "").strip()
    if industry in REGULATED_INDUSTRIES and "governance" != drop_tag:
        axes.add("governance")

    return DerivedQuery(
        tau=tau,
        binding_axes=frozenset(axes),
        title=(row.get("title") or "")[:80],
        industry=industry,
    )


@dataclass
class QueryPrior:
    """The empirical query prior: a multiset of DerivedQuery over real deployments."""

    derived: list[DerivedQuery] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.derived)

    def tau_distribution(self) -> dict[str, int]:
        return dict(Counter(d.tau for d in self.derived))

    def axis_binding_frequency(self) -> dict[str, int]:
        """How many deployments bind each axis (the load-bearing distribution)."""
        c: Counter[str] = Counter()
        for d in self.derived:
            for a in d.binding_axes:
                c[a] += 1
        return dict(c)


def build_query_prior(rows: list[dict], drop_tag: str | None = None) -> QueryPrior:
    """Derive the empirical query prior from ZenML rows."""
    return QueryPrior(derived=[derive_query(r, drop_tag=drop_tag) for r in rows])


# ---------------------------------------------------------------------------
# Turning a DerivedQuery into a runnable Query (with grounded thresholds)
# ---------------------------------------------------------------------------

# op direction per axis: '>=' for "higher is better/required floor",
# '<=' for "lower is better/required ceiling".
_AXIS_OP: dict[str, str] = {
    "quality": ">=",
    "throughput": ">=",
    "governance": ">=",        # nominal — governance is ⊥ everywhere, probes blind spot
    "reviewer_burden": "<=",   # nominal — ⊥ everywhere
    "memory_hw": "<=",
    "latency_p95": "<=",
    "cost": "<=",
    "energy": "<=",
}


def to_query(
    dq: DerivedQuery,
    thresholds: dict[tuple[str, str], float],
    nominal: float = 1.0,
) -> Query:
    """Build a runnable Query from a DerivedQuery.

    Args:
        dq: the derived query.
        thresholds: map (tau, axis) -> grounded threshold (e.g. median observed
            value). Axes absent from the map (⊥ axes) use *nominal*.
        nominal: threshold for ⊥ axes (the bind still probes decidability).
    """
    constraints: list[tuple[str, str, float]] = []
    for axis in sorted(dq.binding_axes):
        op = _AXIS_OP.get(axis, ">=")
        target = thresholds.get((dq.tau, axis), nominal)
        constraints.append((axis, op, target))
    label = "bind:" + "+".join(sorted(dq.binding_axes))
    return make_query(dq.tau, constraints, label=label)
