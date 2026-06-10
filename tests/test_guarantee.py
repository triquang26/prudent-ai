"""Tests for the §9 coverage guarantee (CoverageGuarantee)."""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.solver import Phi, make_query
from prudent_ai.solver.guarantee import CoverageGuarantee
from prudent_ai.solver.regimes import FULL
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


def _seed(sub: Substrate) -> None:
    """Three configs on tau='svc': a clear cheap-feasible winner + a runner-up + a dear one."""
    s = sub._session
    _i(s, Source, evidence_id="src", source_type="leaderboard", citation="x",
       snapshot_version="1")
    rows = [
        # (config, quality, latency, cost)
        ("a", 0.9, 50.0, 1.0),
        ("b", 0.9, 60.0, 2.0),
        ("c", 0.9, 70.0, 3.0),
    ]
    for cid, q, lat, cost in rows:
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="svc")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")
        for axis, val, oid in (("quality", q, f"{cid}-q"),
                               ("latency_p95", lat, f"{cid}-l"),
                               ("cost", cost, f"{cid}-c")):
            _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
               value_cat=None, confidence="H", evidence_id="src",
               hardware_tier="hw", dataset="d", split="test",
               decoding_cfg="greedy", obs_date="2026")
    s.commit()


def _queries():
    return [
        make_query("svc", [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0)],
                   label="decidable"),
        make_query("svc", [("quality", ">=", 0.8), ("energy", "<=", 100.0)],
                   label="energy-blocked"),  # energy ⊥ → abstain
    ]


def test_curve_is_monotone_coverage():
    """Coverage is non-increasing as the commit margin tightens."""
    sub = Substrate(":memory:")
    _seed(sub)
    g = CoverageGuarantee(sub, _queries(), regime=FULL, phi=Phi.POINT)
    curve = g.coverage_risk_curve()
    sub.close()
    covs = [p.coverage for p in curve]
    assert all(covs[i] >= covs[i + 1] for i in range(len(covs) - 1))


def test_decidable_commit_is_correct_under_proxy():
    """The decidable query commits config 'a' and it is proxy-correct (risk 0 at m=0)."""
    sub = Substrate(":memory:")
    _seed(sub)
    g = CoverageGuarantee(sub, _queries(), regime=FULL, phi=Phi.POINT)
    pt0 = g.evaluate_at_margin(0.0)
    sub.close()
    assert pt0.n_commit >= 1          # the decidable query commits
    assert pt0.risk == 0.0            # and is correct under proxy-truth


def test_calibrate_returns_margin_meeting_alpha():
    sub = Substrate(":memory:")
    _seed(sub)
    g = CoverageGuarantee(sub, _queries(), regime=FULL, phi=Phi.POINT)
    cal = g.calibrate(alpha=0.1)
    sub.close()
    assert cal.risk <= 0.1
    assert cal.margin is not None
    assert 0.0 <= cal.coverage <= 1.0


def test_abstain_queries_never_counted_as_commits():
    """The energy-blocked query abstains → contributes 0 to coverage."""
    sub = Substrate(":memory:")
    _seed(sub)
    only_abstain = [make_query("svc", [("quality", ">=", 0.8), ("energy", "<=", 100.0)])]
    g = CoverageGuarantee(sub, only_abstain, regime=FULL, phi=Phi.POINT)
    pt = g.evaluate_at_margin(0.0)
    sub.close()
    assert pt.n_commit == 0
    assert pt.coverage == 0.0
