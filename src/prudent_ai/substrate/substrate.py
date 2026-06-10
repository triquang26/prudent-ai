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

import sqlite3
from dataclasses import dataclass
from pathlib import Path

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

_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class Substrate:
    """Thin evidential data layer for APT.

    Opens (or creates) a SQLite database, enforces foreign-key integrity, and
    initialises the schema.  All query methods are κ-free and φ-free.

    Args:
        db_path: Path to a SQLite file, or ``":memory:"`` for an in-process DB.
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        # Must be run per-connection, not stored in the schema file.
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self.load_schema()

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def load_schema(self, schema_path: Path | None = None) -> None:
        """Execute the DDL from *schema_path* (default: the bundled schema.sql)."""
        path = schema_path if schema_path is not None else _SCHEMA_FILE
        ddl = Path(path).read_text(encoding="utf-8")
        # executescript handles multi-statement SQL natively (including comments)
        # and issues an implicit COMMIT before running.  We re-enable FK enforcement
        # afterwards because executescript resets connection-level PRAGMAs.
        self._conn.executescript(ddl)
        self._conn.execute("PRAGMA foreign_keys = ON;")

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

        # Fetch all configs for this tau.
        config_rows = self._conn.execute(
            "SELECT id, tau FROM config WHERE tau = ?", (tau,)
        ).fetchall()

        result: list[Candidate] = []
        for cfg in config_rows:
            comp_rows = self._conn.execute(
                """
                SELECT comp.id, comp.kind, comp.name
                FROM config_component cc
                JOIN component comp ON comp.id = cc.component_id
                WHERE cc.config_id = ?
                ORDER BY comp.id
                """,
                (cfg["id"],),
            ).fetchall()
            components = tuple(
                ComponentRef(id=r["id"], kind=r["kind"], name=r["name"])
                for r in comp_rows
            )
            result.append(Candidate(id=cfg["id"], tau=cfg["tau"], components=components))

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
        rows = self._conn.execute(
            """
            SELECT
                o.obs_id,
                o.config_id,
                o.axis,
                o.value_num,
                o.value_cat,
                o.confidence,
                o.evidence_id,
                s.source_type,
                o.hardware_tier,
                o.dataset,
                o.split,
                o.decoding_cfg,
                o.obs_date
            FROM observation o
            JOIN source s ON s.evidence_id = o.evidence_id
            WHERE o.config_id = ? AND o.axis = ?
            """,
            (x, a),
        ).fetchall()

        # Invariant: no confidence filtering is performed here.
        observations: list[Observation] = []
        for r in rows:
            ctx = Context(
                hardware_tier=r["hardware_tier"],
                dataset=r["dataset"],
                split=r["split"],
                decoding_cfg=r["decoding_cfg"],
                obs_date=r["obs_date"],
            )
            observations.append(
                Observation(
                    obs_id=r["obs_id"],
                    config_id=r["config_id"],
                    axis=r["axis"],
                    value_num=r["value_num"],
                    value_cat=r["value_cat"],
                    confidence=r["confidence"],
                    evidence_id=r["evidence_id"],
                    source_type=r["source_type"],
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
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> Substrate:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
