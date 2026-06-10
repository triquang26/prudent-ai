"""W1 per-instance binding tests — the Pareto active-constraint test.

On the controlled GT slice (cheap=low-quality, dear=high-quality), the quality
constraint is BINDING at a tight threshold (relaxing it lets the cheaper low-quality
config win → min-cost drops) and SLACK at a loose threshold (the cheap config is
already feasible → relaxing changes nothing). The binding test must separate the two.
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.solver import Phi, make_query
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import Component, Config, ConfigComponent, Source
from prudent_ai.substrate.orm import Observation as ObsORM
from prudent_ai.validation.binding import binding_axes, is_pareto_binding, min_cost


def _i(session, model, **kw):
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed(sub: Substrate) -> None:
    """(cost, quality): cheap=(1.0,0.50), mid=(5.0,0.80), dear=(9.0,0.95)."""
    s = sub._session
    _i(s, Source, evidence_id="gt", source_type="benchmark", citation="gt",
       snapshot_version="1")
    for cid, cost, q in [("cheap", 1.0, 0.50), ("mid", 5.0, 0.80), ("dear", 9.0, 0.95)]:
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gt")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")
        for axis, val, oid in (("cost", cost, f"{cid}-c"), ("quality", q, f"{cid}-q")):
            _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
               value_cat=None, confidence="H", evidence_id="gt", hardware_tier="hw",
               dataset="d", split="test", decoding_cfg="x", obs_date="2026")
    s.commit()


_K = ("H",)
_P = Phi.POINT


def test_quality_binds_at_tight_threshold():
    """quality>=0.8: full min-cost = mid(5); drop quality → cheap(1) < 5 ⇒ BINDING."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = make_query("gt", [("quality", ">=", 0.8)], label="tight")
    assert min_cost(sub, q, _K, _P) == 5.0
    assert min_cost(sub, q, _K, _P, skip="quality") == 1.0
    assert is_pareto_binding(sub, q, "quality", _K, _P) is True
    assert binding_axes(sub, q, _K, _P) == frozenset({"quality"})
    sub.close()


def test_quality_slack_at_loose_threshold():
    """quality>=0.4: cheap(0.5) already feasible → drop changes nothing ⇒ NON-binding."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = make_query("gt", [("quality", ">=", 0.4)], label="loose")
    assert min_cost(sub, q, _K, _P) == 1.0
    assert min_cost(sub, q, _K, _P, skip="quality") == 1.0
    assert is_pareto_binding(sub, q, "quality", _K, _P) is False
    assert binding_axes(sub, q, _K, _P) == frozenset()
    sub.close()


def test_binding_requires_a_feasible_optimum():
    """An infeasible query (quality>=0.99) has no optimum ⇒ no axis reported binding."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = make_query("gt", [("quality", ">=", 0.99)], label="infeasible")
    assert min_cost(sub, q, _K, _P) is None
    assert is_pareto_binding(sub, q, "quality", _K, _P) is False
    sub.close()
