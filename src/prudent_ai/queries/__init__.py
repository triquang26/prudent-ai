"""Empirical query-prior derivation (closes P3 gate Q2).

Derives a real-traffic distribution over right-sizing queries q=(τ, c) from the
ZenML LLMOps Database, via a documented, conservative tag→axis taxonomy.
"""

from prudent_ai.queries.query_prior import (
    ARCHETYPE_MAP,
    REGULATED_INDUSTRIES,
    TAG_TO_AXIS,
    DerivedQuery,
    QueryPrior,
    build_query_prior,
    derive_query,
    to_query,
)
from prudent_ai.queries.zenml_client import ZenMLClient

__all__ = [
    "ARCHETYPE_MAP",
    "REGULATED_INDUSTRIES",
    "TAG_TO_AXIS",
    "DerivedQuery",
    "QueryPrior",
    "ZenMLClient",
    "build_query_prior",
    "derive_query",
    "to_query",
]
