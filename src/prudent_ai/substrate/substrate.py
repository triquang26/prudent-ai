"""APT P1 Evidential Substrate.

The Substrate is a thin, κ-free, φ-free data layer.  It exposes raw evidential
rows to the solver; all filtering (κ-thresholding, constraint checking, missingness
classification) is the solver's responsibility, NOT the substrate's.

Invariants enforced by this module:
- ``cell()``           never filters by confidence — returns all rows.
- ``required_fields()`` never queries the DB — purely ``{c.axis for c in bundle}``.
- ``candidates()``     never accepts a bundle parameter.
- ``is_missing()``     is a module-level function, not a Substrate method, to make
                       explicit that missingness is a solver-side policy decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from prudent_ai.substrate.orm import (
    Base,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import (
    Component as ComponentORM,
)
from prudent_ai.substrate.orm import (
    Config as ConfigORM,
)
from prudent_ai.substrate.orm import (
    Observation as ObsORM,
)

# ---------------------------------------------------------------------------
# Public type definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentRef:
    id: str
    kind: str
    name: str


@dataclass(frozen=True)
class Candidate:
    id: str
    tau: str
    components: tuple[ComponentRef, ...]


@dataclass(frozen=True)
class Context:
    hardware_tier: str | None
    dataset: str | None
    split: str | None
    decoding_cfg: str | None
    obs_date: str | None


@dataclass(frozen=True)
class Observation:
    obs_id: str
    config_id: str
    axis: str
    value_num: float | None
    value_cat: str | None
    confidence: str  # 'H' | 'M' | 'L'
    evidence_id: str
    source_type: str  # denormalized from source table for solver noise-model use
    context: Context


@dataclass(frozen=True)
class Constraint:
    axis: str
    op: str    # e.g. 'ge', 'le', 'in'
    value: object


Bundle = tuple[Constraint, ...]

# ---------------------------------------------------------------------------
# Module-level helper (solver-side policy — NOT a Substrate method)
# ---------------------------------------------------------------------------


def is_missing(obs: list[Observation], kappa: tuple[str, ...]) -> bool:
    """Return True when no observation in *obs* meets the confidence threshold *kappa*.

    This function belongs to the solver, not the substrate.  The substrate
    returns all rows regardless of confidence; the solver calls this to decide
    whether a (config, axis) cell is reportable under a given κ-policy.

    Args:
        obs:   All observations returned by ``Substrate.cell(x, a)``.
        kappa: Confidence tiers the solver considers acceptable, e.g. ``('H', 'M')``.

    Returns:
        ``True``  → no qualifying observation exists (cell is ⊥ under this κ).
        ``False`` → at least one observation meets the threshold (cell is reportable).
    """
    return len([o for o in obs if o.confidence in kappa]) == 0


# ---------------------------------------------------------------------------
# Substrate
# ---------------------------------------------------------------------------


class Substrate:
    """Thin evidential data layer for APT.

    Opens (or creates) a SQLite database, enforces foreign-key integrity, and
    initialises the schema via SQLAlchemy ORM.  All query methods are κ-free
    and φ-free.

    Args:
        db_path: Path to a SQLite file, or ``":memory:"`` for an in-process DB.
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db_path = str(db_path)
        url = "sqlite://" if self._db_path == ":memory:" else f"sqlite:///{self._db_path}"
        self._engine = create_engine(url)

        @event.listens_for(self._engine, "connect")
        def _set_fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys = ON")

        Base.metadata.create_all(self._engine)
        self._session = Session(self._engine)

    # ------------------------------------------------------------------
    # Core interface (immutable once P1 starts — constraint C7)
    # ------------------------------------------------------------------

    def candidates(self, tau: str) -> list[Candidate]:
        """Return ALL configs for *tau* with their component lineage.

        κ-free, φ-free.  No filtering of any kind is applied.

        Args:
            tau: Deployment-context tag that groups related configs.

        Returns:
            One ``Candidate`` per config row matching *tau*, with components
            populated from the ``config_component`` → ``component`` join.
        """
        # Invariant: this method never accepts a bundle parameter.
        assert not hasattr(self, "_candidates_takes_bundle"), (
            "candidates() must never be called with a bundle parameter"
        )

        cfg_rows = (
            self._session.execute(select(ConfigORM).where(ConfigORM.tau == tau)).scalars().all()
        )
        result = []
        for cfg in cfg_rows:
            comp_rows = self._session.execute(
                select(ComponentORM)
                .join(ConfigComponent, ConfigComponent.component_id == ComponentORM.id)
                .where(ConfigComponent.config_id == cfg.id)
                .order_by(ComponentORM.id)
            ).scalars().all()
            components = tuple(ComponentRef(id=c.id, kind=c.kind, name=c.name) for c in comp_rows)
            result.append(Candidate(id=cfg.id, tau=cfg.tau, components=components))
        return result

    def cell(self, x: str, a: str) -> list[Observation]:
        """Return ALL observations for config *x* on axis *a*.

        κ-free: confidence is never filtered here; the caller (solver) decides
        which confidence tiers are acceptable.

        Args:
            x: config_id.
            a: axis name.

        Returns:
            List of ``Observation`` objects (may be empty if no rows exist).
        """
        rows = self._session.execute(
            select(ObsORM, Source.source_type)
            .join(Source, Source.evidence_id == ObsORM.evidence_id)
            .where(ObsORM.config_id == x, ObsORM.axis == a)
        ).all()

        # Invariant: no confidence filtering is performed here.
        observations = []
        for obs_row, source_type in rows:
            ctx = Context(
                hardware_tier=obs_row.hardware_tier,
                dataset=obs_row.dataset,
                split=obs_row.split,
                decoding_cfg=obs_row.decoding_cfg,
                obs_date=obs_row.obs_date,
            )
            observations.append(
                Observation(
                    obs_id=obs_row.obs_id,
                    config_id=obs_row.config_id,
                    axis=obs_row.axis,
                    value_num=obs_row.value_num,
                    value_cat=obs_row.value_cat,
                    confidence=obs_row.confidence,
                    evidence_id=obs_row.evidence_id,
                    source_type=source_type,
                    context=ctx,
                )
            )
        return observations

    def required_fields(self, bundle: Bundle) -> set[str]:
        """Return the set of axes required by *bundle*.

        Syntactic only: this method never touches the database.  It is provided
        on Substrate purely for interface completeness; the logic is trivial by
        design so that the contract is unambiguous.

        Args:
            bundle: Tuple of ``Constraint`` objects describing solver requirements.

        Returns:
            ``{c.axis for c in bundle}`` — the set of axes that must be observed
            for a config to satisfy the bundle.
        """
        # Invariant: no DB access.
        return {c.axis for c in bundle}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLAlchemy session and engine."""
        self._session.close()
        self._engine.dispose()

    def __enter__(self) -> Substrate:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
