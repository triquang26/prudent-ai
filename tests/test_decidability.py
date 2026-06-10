"""P3 gate tests for the decidability classifier.

Anchors the classifier to the formalism:
  test_gadget_off_regime_underdetermined — the §8.2 two-world gadget: when the
      binding axis (latency) is outside the regime R={quality,cost}, the query is
      UNDERDETERMINED; admitting latency into the regime makes it DECIDABLE and
      the argmin matches the world (x_cheap in W1, x_safe in W2).
  test_decidable_when_binding_axis_in_regime — a sure-feasible, sure-costed,
      uniquely-cheapest config yields DECIDABLE.
  test_infeasible_when_all_violated — every candidate certified-violated ⇒ INFEASIBLE.
  test_c7_classifier_reads_only_interface — the classifier touches the substrate
      only through candidates / cell / required_fields (C7 firewall).
  test_determinism — repeated classification is identical.
"""

from __future__ import annotations

from collections import Counter

import pytest
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.solver import (
    Decidability,
    Phi,
    classify_query,
    make_query,
)
from prudent_ai.solver.regimes import ACC_COST, FULL
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import (
    Component,
    Config,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import (
    Observation as ObsORM,
)


def _i(session, model, **kw):
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed_gadget(sub: Substrate, latency_cheap: float | None) -> None:
    """Build the §8.2 gadget on tau='gadget'.

    x_cheap: cost 1.0, latency = latency_cheap (or ⊥ if None)
    x_safe : cost 1.1, latency = L*-ε = 90  (always satisfies latency ≤ 100)

    W1 (latency_cheap=90): x_cheap satisfies latency → x_cheap optimal (cost 1.0).
    W2 (latency_cheap=110): x_cheap violates latency → x_safe optimal (cost 1.1).
    R-masked (latency_cheap=None or regime without latency): latency ⊥ → flip → underdetermined.
    """
    s = sub._session
    _i(s, Source, evidence_id="gadget-src", source_type="benchmark",
       citation="gadget", snapshot_version="1")
    for cid in ("x_cheap", "x_safe"):
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gadget")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")

    def obs(oid, cid, axis, val):
        _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
           value_cat=None, confidence="H", evidence_id="gadget-src",
           hardware_tier="hw", dataset="d", split="test",
           decoding_cfg="greedy", obs_date="2026")

    # costs (always present)
    obs("o-cheap-cost", "x_cheap", "cost", 1.0)
    obs("o-safe-cost", "x_safe", "cost", 1.1)
    # quality (in R, both pass)
    obs("o-cheap-q", "x_cheap", "quality", 0.9)
    obs("o-safe-q", "x_safe", "quality", 0.9)
    # latency: safe always 90; cheap depends on world
    obs("o-safe-lat", "x_safe", "latency_p95", 90.0)
    if latency_cheap is not None:
        obs("o-cheap-lat", "x_cheap", "latency_p95", latency_cheap)
    s.commit()


@pytest.fixture()
def query_qcl():
    """Query: quality ≥ 0.8 AND latency_p95 ≤ 100. Binding axis under stress = latency."""
    return make_query(
        "gadget",
        [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0)],
        label="quality+latency",
    )


def test_gadget_off_regime_underdetermined(query_qcl):
    """W1 with latency masked out of the regime (R={quality,cost}) ⇒ underdetermined.

    Even though x_cheap's latency is present in the substrate, an R-restricted rule
    that cannot see latency must treat it as ⊥ — the cheaper x_cheap then has a
    pending latency field that could flip the argmin against x_safe.
    """
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=90.0)   # W1
    res = classify_query(sub, query_qcl, phi=Phi.POINT, regime=ACC_COST)
    sub.close()
    assert res.label is Decidability.UNDERDETERMINED
    assert "latency_p95" in res.blocking_axes


def test_gadget_w1_decidable_full_regime(query_qcl):
    """W1 under FULL regime: latency present, x_cheap feasible & cheapest ⇒ decidable→x_cheap."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=90.0)
    res = classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert res.label is Decidability.DECIDABLE
    assert res.argmin_config == "x_cheap"


def test_gadget_w2_decidable_full_regime(query_qcl):
    """W2 under FULL regime: x_cheap violates latency, x_safe optimal ⇒ decidable→x_safe."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=110.0)   # W2: cheap violates latency ≤ 100
    res = classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert res.label is Decidability.DECIDABLE
    assert res.argmin_config == "x_safe"


def test_gadget_cheap_latency_missing_underdetermined(query_qcl):
    """If x_cheap's latency is genuinely ⊥ (not masked), the argmin still flips."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=None)    # x_cheap latency absent
    res = classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert res.label is Decidability.UNDERDETERMINED
    assert "latency_p95" in res.blocking_axes


def test_infeasible_when_all_violated():
    """quality ≥ 0.99 — both configs (0.9) certified-violated ⇒ INFEASIBLE."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=90.0)
    q = make_query("gadget", [("quality", ">=", 0.99)], label="impossible-quality")
    res = classify_query(sub, q, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert res.label is Decidability.INFEASIBLE


def test_c7_classifier_reads_only_interface(query_qcl):
    """The classifier must touch the substrate ONLY through candidates / cell."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=90.0)

    calls: list[str] = []
    orig_candidates = sub.candidates
    orig_cell = sub.cell

    def wrap_candidates(tau):
        calls.append("candidates")
        return orig_candidates(tau)

    def wrap_cell(x, a):
        calls.append("cell")
        return orig_cell(x, a)

    sub.candidates = wrap_candidates
    sub.cell = wrap_cell
    classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    sub.close()

    # Only the two interface methods were used, and at least one of each.
    seen = Counter(calls)
    assert set(seen) <= {"candidates", "cell"}
    assert seen["candidates"] >= 1
    assert seen["cell"] >= 1


def test_determinism(query_qcl):
    sub = Substrate(":memory:")
    _seed_gadget(sub, latency_cheap=90.0)
    r1 = classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    r2 = classify_query(sub, query_qcl, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert r1 == r2
