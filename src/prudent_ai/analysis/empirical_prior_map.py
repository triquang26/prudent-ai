"""Empirical-prior decidability map (P3 gate Q2) — reweight DV1 by real traffic.

P3's headline "% underdetermined" was, until now, conditional on a *hand-built*
query grid (`decidability_map.generate_queries`): every axis probed once plus a
curated set of pairwise bundles. That makes the number honest but not
representative — it says nothing about how *real* deployment traffic distributes
over binding axes.

This module closes that gap. It takes the **empirical query prior** derived from
1716 real LLM-deployment case studies (ZenML LLMOps Database; see
`prudent_ai.queries.query_prior`) and runs the same C7-firewalled decidability
classifier over that real-traffic multiset of queries. The deliverables:

  1. `load_prior`          — fetch ZenML rows once, build the empirical prior.
  2. `grounded_thresholds` — median (p50) observed value per (τ, axis), reusing
                             `decidability_map.observed_thresholds` (C7 interface).
  3. `empirical_map`       — for every regime in `REGIME_LADDER`, classify every
                             derived query and tally decidable / underdetermined /
                             infeasible fractions + counts + 95% bootstrap CI +
                             blocking-axis tally.
  4. `attribution`         — of the underdetermined queries, the blocking-axis
                             frequency, AND the fraction of ALL queries whose
                             underdetermination is attributable to a 100%-⊥ axis
                             (governance / reviewer_burden / memory_hw / energy /
                             throughput). This is the load-bearing "real traffic
                             binds on unmeasurable axes" number.
  5. `grid_vs_empirical`   — headline FULL-regime %underdetermined under the P3
                             hand grid vs this empirical prior.
  6. `mapping_sensitivity` — drop-one-tag robustness: no single tag→axis mapping
                             carries the finding.

C7 firewall. Every decidability verdict goes through `classify_query`
(→ `classify_candidate` → `sub.candidates`/`sub.cell`). The thresholds are read
through `observed_thresholds` (also C7). No raw SQL feeds any verdict.

Determinism. Bootstrap resampling is seeded with `random.Random(12345)` (reusing
`decidability_map.bootstrap_ci`), so the whole map is reproducible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prudent_ai.analysis.decidability_map import (
    bootstrap_ci,
    generate_queries,
    observed_thresholds,
    run_cell,
)
from prudent_ai.queries import ZenMLClient, build_query_prior, to_query
from prudent_ai.solver import (
    FULL,
    REGIME_LADDER,
    Decidability,
    Phi,
    classify_query,
)

if TYPE_CHECKING:
    from prudent_ai.queries.query_prior import QueryPrior
    from prudent_ai.substrate import Substrate

# Stable label ordering for tallies / JSON.
_DEC = Decidability.DECIDABLE.value
_UND = Decidability.UNDERDETERMINED.value
_INF = Decidability.INFEASIBLE.value
_LABELS: tuple[str, ...] = (_DEC, _UND, _INF)

# Percentile used to ground thresholds (median = realistic mid-bar). Matches the
# hand-grid in decidability_map so grid-vs-empirical compares like with like.
_GRID_PCT: int = 50

# Axes that are ⊥ (no κ-qualifying evidence) in EVERY archetype of the substrate.
# governance / reviewer_burden / energy / throughput carry zero observations;
# memory_hw is effectively unmeasured (only 20/1716 bindings, all general-qa with
# no candidate-level evidence). Underdetermination attributable to one of these is
# structural: it cannot be resolved by any amount of in-regime evidence because the
# axis is unmeasured corpus-wide. This is the "real traffic binds on unmeasurable
# axes" load-bearing set.
UNMEASURABLE_AXES: frozenset[str] = frozenset(
    {"governance", "reviewer_burden", "memory_hw", "energy", "throughput"}
)

# Tags swept by mapping_sensitivity (drop-one robustness). 'governance' is the
# industry rule (REGULATED_INDUSTRIES), the rest are TAG_TO_AXIS entries.
_SENSITIVITY_TAGS: tuple[str, ...] = (
    "latency_optimization",
    "cost_optimization",
    "regulatory_compliance",
    "high_stakes_application",
    "human_in_the_loop",
    "governance",
)


# ---------------------------------------------------------------------------
# 1. Load the empirical prior
# ---------------------------------------------------------------------------


# Frozen snapshot of the ZenML corpus (C3: versioned, reproducible). Fetched
# once; subsequent runs read it from disk instead of re-querying the server.
ZENML_SNAPSHOT = "data/zenml_llmops_snapshot.json"


def load_prior(
    limit: int | None = None, cache_path: str | None = ZENML_SNAPSHOT
) -> tuple[list[dict], QueryPrior]:
    """Load the ZenML rows (from the frozen snapshot if present) and build the prior.

    Returns ``(rows, prior)`` so callers can rebuild the prior under drop-one-tag
    ablations (mapping_sensitivity) without re-fetching.
    """
    rows = ZenMLClient().fetch_all_rows(limit=limit, cache_path=cache_path)
    prior = build_query_prior(rows)
    return rows, prior


# ---------------------------------------------------------------------------
# 2. Grounded thresholds (median observed, through the C7 interface)
# ---------------------------------------------------------------------------


def grounded_thresholds(
    sub: Substrate,
    taus: list[str],
    axes: list[str],
    kappa: tuple[str, ...] = ("H", "M"),
) -> dict[tuple[str, str], float]:
    """Median (p50) observed value per (τ, axis), via `observed_thresholds`.

    Reads the substrate ONLY through the C7 interface (observed_thresholds iterates
    `sub.candidates`/`sub.cell`). Axes with no κ-qualifying evidence for a τ are
    *omitted* from the returned map — `to_query` falls back to the nominal
    threshold for those (the bind still probes decidability; that ⊥ axis is exactly
    where the empirical prior bites).
    """
    out: dict[tuple[str, str], float] = {}
    for tau in taus:
        for axis in axes:
            pcts = observed_thresholds(sub, tau, axis, (_GRID_PCT,), kappa)
            if _GRID_PCT in pcts:
                out[(tau, axis)] = pcts[_GRID_PCT]
    return out


# ---------------------------------------------------------------------------
# 3. The empirical decidability map (over the real-traffic prior)
# ---------------------------------------------------------------------------


def _classify_prior(
    sub: Substrate,
    prior: QueryPrior,
    thresholds: dict[tuple[str, str], float],
    regime: frozenset[str],
    kappa: tuple[str, ...],
    phi: Phi,
) -> dict:
    """Classify every derived query under one regime; tally outcomes.

    Returns the same shape as `decidability_map.run_cell`:
    ``{n, counts, fractions, labels, blocking}`` where ``blocking[label]`` is the
    per-outcome blocking-axis frequency.
    """
    labels: list[str] = []
    counts: dict[str, int] = dict.fromkeys(_LABELS, 0)
    blocking: dict[str, dict[str, int]] = {lab: {} for lab in _LABELS}

    for dq in prior.derived:
        query = to_query(dq, thresholds)
        res = classify_query(sub, query, kappa=kappa, phi=phi, regime=regime)
        lab = res.label.value
        labels.append(lab)
        counts[lab] += 1
        for ax in res.blocking_axes:
            blocking[lab][ax] = blocking[lab].get(ax, 0) + 1

    n = len(labels)
    fractions = {lab: (counts[lab] / n if n else 0.0) for lab in _LABELS}
    return {
        "n": n,
        "counts": counts,
        "fractions": fractions,
        "labels": labels,
        "blocking": blocking,
    }


def empirical_map(
    sub: Substrate,
    prior: QueryPrior,
    thresholds: dict[tuple[str, str], float],
    kappa: tuple[str, ...] = ("H", "M"),
    phi: Phi = Phi.POINT,
    n_boot: int = 1000,
) -> dict:
    """Empirical-prior decidability map over the regime ladder (§5 / DV1).

    For each regime in `REGIME_LADDER`, classify every derived query in the prior
    and report fractions / counts / 95% bootstrap CI / blocking-axis tally.

    Returns ``{regime_name: {fractions, cis, counts, blocking, n}}``.
    """
    out: dict[str, dict] = {}
    for regime_name, regime in REGIME_LADDER:
        cell = _classify_prior(sub, prior, thresholds, regime, kappa, phi)
        cis = bootstrap_ci(cell["labels"], n_boot=n_boot)
        out[regime_name] = {
            "n": cell["n"],
            "fractions": cell["fractions"],
            "cis": cis,
            "counts": cell["counts"],
            "blocking": cell["blocking"],
        }
    return out


# ---------------------------------------------------------------------------
# 4. Attribution — what fraction is structurally unresolvable?
# ---------------------------------------------------------------------------


def attribution(
    sub: Substrate,
    prior: QueryPrior,
    thresholds: dict[tuple[str, str], float],
    regime: frozenset[str] = FULL,
    kappa: tuple[str, ...] = ("H", "M"),
    phi: Phi = Phi.POINT,
) -> dict:
    """Attribute underdetermination to unmeasurable axes (load-bearing number).

    Of the underdetermined queries (under *regime*), report:
      - ``blocking_axis_frequency``: how often each axis appears in a blocking set.
      - ``frac_underdetermined``: %underdetermined over ALL queries.
      - ``frac_attributable_unmeasurable``: fraction of ALL queries that are
        underdetermined AND blocked by at least one 100%-⊥ axis
        (`UNMEASURABLE_AXES`). This is "real traffic binds on unmeasurable axes":
        the underdetermination is *structural*, not curable by more in-regime data.
      - ``frac_attributable_only_unmeasurable``: stricter — underdetermined and
        ALL blocking axes are unmeasurable (no measurable axis also blocks).

    Reads the substrate only through `classify_query` (C7).
    """
    n_total = prior.n
    blocking_freq: dict[str, int] = {}
    n_und = 0
    n_attrib_any = 0
    n_attrib_only = 0

    for dq in prior.derived:
        query = to_query(dq, thresholds)
        res = classify_query(sub, query, kappa=kappa, phi=phi, regime=regime)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1
        blk = set(res.blocking_axes)
        for ax in blk:
            blocking_freq[ax] = blocking_freq.get(ax, 0) + 1
        if blk & UNMEASURABLE_AXES:
            n_attrib_any += 1
        if blk and blk <= UNMEASURABLE_AXES:
            n_attrib_only += 1

    ranked = dict(sorted(blocking_freq.items(), key=lambda kv: (-kv[1], kv[0])))
    return {
        "regime": "full" if regime == FULL else "+".join(sorted(regime)),
        "n_total": n_total,
        "n_underdetermined": n_und,
        "frac_underdetermined": (n_und / n_total if n_total else 0.0),
        "blocking_axis_frequency": ranked,
        "unmeasurable_axes": sorted(UNMEASURABLE_AXES),
        "n_attributable_unmeasurable": n_attrib_any,
        "frac_attributable_unmeasurable": (
            n_attrib_any / n_total if n_total else 0.0
        ),
        "n_attributable_only_unmeasurable": n_attrib_only,
        "frac_attributable_only_unmeasurable": (
            n_attrib_only / n_total if n_total else 0.0
        ),
    }


# ---------------------------------------------------------------------------
# 5. Grid vs empirical — does the headline survive real reweighting?
# ---------------------------------------------------------------------------


def grid_vs_empirical(
    sub: Substrate,
    prior: QueryPrior,
    thresholds: dict[tuple[str, str], float],
    kappa: tuple[str, ...] = ("H", "M"),
    phi: Phi = Phi.POINT,
) -> dict:
    """Compare FULL-regime %underdetermined: P3 hand grid vs this empirical prior.

    (a) Hand grid: pool `decidability_map.generate_queries` over every archetype
        and classify each with `run_cell` (FULL regime). This is the *uniform*
        per-axis battery — the original P3 caveat.
    (b) Empirical prior: %underdetermined from the real-traffic multiset.

    The two headlines being close is the point: the qualitative "most decisions are
    underdetermined" finding does not depend on the hand grid; weighting by real
    deployment traffic gives the same answer.
    """
    from prudent_ai.analysis.decidability_map import ARCHETYPES

    # (a) hand grid, pooled over archetypes, FULL regime.
    grid_labels: list[str] = []
    grid_counts: dict[str, int] = dict.fromkeys(_LABELS, 0)
    for tau in ARCHETYPES(sub):
        queries = generate_queries(sub, tau, kappa)
        cell = run_cell(sub, tau, FULL, kappa, phi, queries)
        grid_labels.extend(cell["labels"])
        for lab in _LABELS:
            grid_counts[lab] += cell["counts"][lab]
    n_grid = len(grid_labels)
    grid_frac = {
        lab: (grid_counts[lab] / n_grid if n_grid else 0.0) for lab in _LABELS
    }

    # (b) empirical prior, FULL regime.
    emp = _classify_prior(sub, prior, thresholds, FULL, kappa, phi)

    return {
        "regime": "full",
        "grid": {
            "n": n_grid,
            "counts": grid_counts,
            "fractions": grid_frac,
            "underdetermined": grid_frac[_UND],
        },
        "empirical": {
            "n": emp["n"],
            "counts": emp["counts"],
            "fractions": emp["fractions"],
            "underdetermined": emp["fractions"][_UND],
        },
        "delta_underdetermined": emp["fractions"][_UND] - grid_frac[_UND],
    }


# ---------------------------------------------------------------------------
# 6. Mapping sensitivity — drop-one-tag robustness
# ---------------------------------------------------------------------------


def mapping_sensitivity(
    sub: Substrate,
    rows: list[dict],
    thresholds: dict[tuple[str, str], float],
    kappa: tuple[str, ...] = ("H", "M"),
    phi: Phi = Phi.POINT,
) -> dict:
    """Drop-one-tag robustness of the FULL-regime %underdetermined headline.

    For each tag in `_SENSITIVITY_TAGS` (the five highest-leverage TAG_TO_AXIS
    entries plus the 'governance' industry rule), rebuild the prior with
    `build_query_prior(rows, drop_tag=...)`, recompute FULL-regime
    %underdetermined, and report the delta vs the baseline (no drop). Small deltas
    ⇒ no single mapping choice carries the finding (C8 robustness).

    Returns ``{baseline: f, by_dropped_tag: {tag: {frac, delta}}}``.
    """
    base_prior = build_query_prior(rows)
    base_cell = _classify_prior(sub, base_prior, thresholds, FULL, kappa, phi)
    baseline = base_cell["fractions"][_UND]

    by_tag: dict[str, dict] = {}
    for tag in _SENSITIVITY_TAGS:
        prior = build_query_prior(rows, drop_tag=tag)
        cell = _classify_prior(sub, prior, thresholds, FULL, kappa, phi)
        frac = cell["fractions"][_UND]
        by_tag[tag] = {
            "underdetermined": frac,
            "delta": frac - baseline,
            "n": cell["n"],
        }

    return {
        "regime": "full",
        "baseline_underdetermined": baseline,
        "by_dropped_tag": by_tag,
    }


__all__ = [
    "UNMEASURABLE_AXES",
    "attribution",
    "empirical_map",
    "grid_vs_empirical",
    "grounded_thresholds",
    "load_prior",
    "mapping_sensitivity",
]
