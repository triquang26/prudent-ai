"""Analysis layer — decidability map, blind-spot, and sensitivity (§5 / H2 / H3).

Sits to the RIGHT of the C7 firewall: every decidability computation reads the
substrate only through the solver (`candidates` / `cell` / `required_fields`).
The descriptive blind-spot miss-rate and τ discovery read the raw DB directly and
are explicitly labelled descriptive provenance.
"""

from prudent_ai.analysis.decidability_map import (
    ARCHETYPES,
    AXES,
    blind_spot_report,
    bootstrap_ci,
    build_map,
    generate_queries,
    observed_thresholds,
    run_cell,
    sensitivity_kappa,
)

__all__ = [
    "ARCHETYPES",
    "AXES",
    "blind_spot_report",
    "bootstrap_ci",
    "build_map",
    "generate_queries",
    "observed_thresholds",
    "run_cell",
    "sensitivity_kappa",
]
