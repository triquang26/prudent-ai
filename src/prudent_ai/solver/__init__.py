"""Solver layer — everything to the RIGHT of the C7 firewall (§9).

Reads the substrate ONLY through `candidates / cell / required_fields`. All
aggregation (φ), confidence filtering (κ), evidence-regime masking (R),
feasibility certification, and decidability classification live here — never in
the substrate.

Public surface:
  beliefs       — Agg_φ(O_E | κ): derive a Belief or ⊥ from an observation set.
  regimes       — evidence regimes R ⊆ A and the IV ablation ladder.
  feasibility   — three-state per-candidate classifier (§4).
  decidability  — query-level decidable/underdetermined/infeasible (§5).
  query         — Query (τ, bundle) and constructors.
"""

from prudent_ai.solver.beliefs import (
    BOTTOM,
    DEFAULT_KAPPA,
    Belief,
    Phi,
    aggregate,
    kappa_filter,
)
from prudent_ai.solver.decidability import (
    Decidability,
    DecidabilityResult,
    classify_query,
)
from prudent_ai.solver.feasibility import (
    CandidateVerdict,
    FeasState,
    classify_candidate,
)
from prudent_ai.solver.query import Bundle, Query, make_query
from prudent_ai.solver.regimes import (
    ALL_AXES,
    FULL,
    REGIME_LADDER,
    in_regime,
)

__all__ = [
    "ALL_AXES",
    "BOTTOM",
    "DEFAULT_KAPPA",
    "FULL",
    "REGIME_LADDER",
    "Belief",
    "Bundle",
    "CandidateVerdict",
    "Decidability",
    "DecidabilityResult",
    "FeasState",
    "Phi",
    "Query",
    "aggregate",
    "classify_candidate",
    "classify_query",
    "in_regime",
    "kappa_filter",
    "make_query",
]
