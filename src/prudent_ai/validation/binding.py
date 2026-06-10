"""Per-instance binding via Pareto structure (§1 / §11-Q2, closes the empirical half of W1).

The validation treats a query's *constrained* axes as its binding set. A reviewer's
sharpest attack (mock-review W1) is that a *declared* constraint need not be **active
at the realized optimum**: if relaxing it does not change `x*`, masking it should not
bite, and the C2 result would ride on an over-approximation of binding.

This module recovers `bind(q)` **per instance** from the slice's own Pareto structure
— no tags, no declaration. On a ground-truth slice (true measured values), an axis `a`
is **Pareto-binding** at `q` iff dropping its constraint *strictly lowers* the
achievable minimum cost over truly-feasible configs:

    bind(q) = { a ∈ constrained(q) :  min_cost(q minus a)  <  min_cost(q) }.

This is the standard active-constraint test: a slack (inactive) constraint can be
removed without changing the optimum, an active (binding) one cannot. The C2 mechanism
— a binding axis is hidden ⇒ a blind commit mis-sizes — should hold **iff** the masked
axis is Pareto-binding, giving an independent, data-recovered certificate that the
biting axes really bind.

Reads the substrate ONLY through the C7 interface (`candidates` / `cell`, via
`aggregate`); the GT slice SCOREs, never tunes (C8). Recoverable only where GT exists
(the measurable axes); corpus-wide-⊥ axes stay binding-unrecoverable by construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import DEFAULT_KAPPA, Phi, aggregate

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query

_EPS = 1e-9


def _satisfies(op: str, val: float, target: float) -> bool:
    if op == ">=":
        return val >= target
    if op == "<=":
        return val <= target
    if op == "==":
        return val == target
    return False


def _true_val(sub, cid: str, axis: str, kappa, phi) -> float | None:
    b = aggregate(sub.cell(cid, axis), kappa, phi)
    return b.point if b.is_present else None


def _feasible_except(sub, query: Query, cid: str, kappa, phi, skip: str | None) -> bool:
    """True iff *cid* truly satisfies every bound axis of *query* except *skip*."""
    for con in query.bundle:
        if con.axis == skip:
            continue
        v = _true_val(sub, cid, con.axis, kappa, phi)
        if v is None:
            return False  # truly unknown ⇒ cannot certify feasible
        if not _satisfies(con.op, v, float(con.value)):
            return False
    return True


def min_cost(
    sub, query: Query, kappa=DEFAULT_KAPPA, phi: Phi = Phi.POINT,
    skip: str | None = None,
) -> float | None:
    """True minimum cost over configs feasible under *query* (optionally dropping *skip*).

    Returns None if no config is truly feasible (or none has a known cost).
    """
    best: float | None = None
    for c in sub.candidates(query.tau):
        if not _feasible_except(sub, query, c.id, kappa, phi, skip):
            continue
        cost = _true_val(sub, c.id, "cost", kappa, phi)
        if cost is None:
            continue
        if best is None or cost < best:
            best = cost
    return best


def is_pareto_binding(
    sub, query: Query, axis: str, kappa=DEFAULT_KAPPA, phi: Phi = Phi.POINT,
    eps: float = _EPS,
) -> bool:
    """True iff *axis* is an ACTIVE constraint at the realized optimum of *query*.

    Active ⇔ relaxing (dropping) the constraint on *axis* makes a strictly cheaper
    truly-feasible config available. A slack constraint leaves the optimum unchanged.
    Requires a feasible optimum under the full bundle; an axis whose drop is unmeasured
    (no GT) cannot lower the cost and is reported non-binding (binding-unrecoverable).
    """
    full = min_cost(sub, query, kappa, phi, skip=None)
    if full is None:
        return False
    relaxed = min_cost(sub, query, kappa, phi, skip=axis)
    if relaxed is None:
        return False
    return relaxed < full - eps


def binding_axes(
    sub, query: Query, kappa=DEFAULT_KAPPA, phi: Phi = Phi.POINT,
) -> frozenset[str]:
    """The Pareto-binding (active) subset of *query*'s constrained axes."""
    return frozenset(
        c.axis for c in query.bundle
        if is_pareto_binding(sub, query, c.axis, kappa, phi)
    )
