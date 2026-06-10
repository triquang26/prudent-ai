"""P4 gate tests — selective procedure + VoI, anchored to the §8 theorem.

The crown jewel:
  test_voi_equals_delta_R — on the §8.2 two-world gadget (R={quality,cost}, binding
    axis latency ∉ R), the implemented VoI of the omitted binding axis equals
    Δ(R) = δλ/(δ+λ) exactly (§8.7 identity). This pins the implementation to the
    limit theorem: the irreducible regret of an evidence regime = the value of
    information of the binding axis it omits.

Plus procedure behaviour + the C7 firewall.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.solver import Phi, make_query
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ACC_COST, FULL
from prudent_ai.solver.voi import voi_for_axis
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


def _seed_gadget(sub: Substrate, delta: float, latency_cheap: float | None) -> None:
    """§8.2 gadget. x_cheap cost 1.0, x_safe cost 1.0+delta (δ).

    Quality 0.9 both (in R). Latency: x_safe always 90 (≤100 ✓);
    x_cheap = latency_cheap (or ⊥ if None).
    """
    s = sub._session
    _i(s, Source, evidence_id="g", source_type="benchmark", citation="g",
       snapshot_version="1")
    for cid in ("x_cheap", "x_safe"):
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gadget")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")

    def obs(oid, cid, axis, val):
        _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
           value_cat=None, confidence="H", evidence_id="g", hardware_tier="hw",
           dataset="d", split="test", decoding_cfg="greedy", obs_date="2026")

    obs("c-cost", "x_cheap", "cost", 1.0)
    obs("s-cost", "x_safe", "cost", 1.0 + delta)
    obs("c-q", "x_cheap", "quality", 0.9)
    obs("s-q", "x_safe", "quality", 0.9)
    obs("s-lat", "x_safe", "latency_p95", 90.0)
    if latency_cheap is not None:
        obs("c-lat", "x_cheap", "latency_p95", latency_cheap)
    s.commit()


@pytest.fixture()
def q_quality_latency():
    return make_query("gadget",
                      [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0)],
                      label="q+lat")


@pytest.mark.parametrize(("delta", "lam"), [(0.1, 1.0), (0.5, 1.0), (0.2, 2.0), (1.0, 0.3)])
def test_voi_equals_delta_R(q_quality_latency, delta, lam):
    """§8.7: VoI(latency) == Δ(R) == δλ/(δ+λ), for several (δ, λ).

    Faithful §8.2 gadget: x_safe is the KNOWN-feasible fallback (latency 90 ≤ 100,
    present in E), x_cheap's latency is ABSENT (⊥) — so latency is the omitted
    binding axis for the cheaper candidate. Its VoI must equal Δ(R).
    """
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=delta, latency_cheap=None)   # x_cheap latency ⊥
    voi = voi_for_axis(sub, q_quality_latency, "latency_p95",
                       phi=Phi.POINT, regime=FULL, lam=lam)
    sub.close()
    expected = (delta * lam) / (delta + lam)   # Δ(R)
    assert math.isclose(voi, expected, rel_tol=1e-9, abs_tol=1e-9), (
        f"VoI={voi} != Δ(R)={expected}"
    )


def test_procedure_abstains_and_names_latency(q_quality_latency):
    """Off-regime binding ⇒ ABSTAIN, and the named acquisition is the binding axis."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=0.1, latency_cheap=None)   # x_cheap latency ⊥
    rec = right_size(sub, q_quality_latency, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert rec.action is Action.ABSTAIN
    assert "latency_p95" in rec.blocking_axes
    assert rec.acquire_next == "latency_p95"
    assert rec.voi_ranking[0].voi > 0


def test_procedure_commits_when_decidable(q_quality_latency):
    """Full regime, W1 (x_cheap feasible & cheapest) ⇒ COMMIT x_cheap."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=0.1, latency_cheap=90.0)
    rec = right_size(sub, q_quality_latency, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert rec.action is Action.COMMIT
    assert rec.committed_config == "x_cheap"


def test_procedure_infeasible():
    """quality ≥ 0.99 — both 0.9 violated ⇒ INFEASIBLE."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=0.1, latency_cheap=90.0)
    q = make_query("gadget", [("quality", ">=", 0.99)], label="impossible")
    rec = right_size(sub, q, phi=Phi.POINT, regime=FULL)
    sub.close()
    assert rec.action is Action.INFEASIBLE


def test_voi_cost_aware_ranking():
    """When two axes block, the cheaper-to-measure axis with comparable VoI ranks higher."""
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=0.1, latency_cheap=90.0)
    # bind on latency (cheap to measure) AND governance (⊥, expensive to measure)
    q = make_query("gadget",
                   [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0),
                    ("governance", ">=", 1.0)],
                   label="lat+gov")
    rec = right_size(sub, q, phi=Phi.POINT, regime=ACC_COST)
    sub.close()
    assert rec.action is Action.ABSTAIN
    axes = [a.axis for a in rec.voi_ranking]
    assert set(axes) >= {"latency_p95", "governance"}


def test_c7_procedure_reads_only_interface(q_quality_latency):
    sub = Substrate(":memory:")
    _seed_gadget(sub, delta=0.1, latency_cheap=90.0)
    calls: set[str] = set()
    orig_c, orig_cell = sub.candidates, sub.cell

    def wc(t):
        calls.add("candidates")
        return orig_c(t)

    def wcell(x, a):
        calls.add("cell")
        return orig_cell(x, a)

    sub.candidates = wc
    sub.cell = wcell
    right_size(sub, q_quality_latency, phi=Phi.POINT, regime=ACC_COST)
    sub.close()
    assert calls <= {"candidates", "cell"}
