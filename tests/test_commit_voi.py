"""P5 C3 positive-action tests — COMMIT-branch validity + scaled VoI (W11).

On a controlled slice where cheap=low-quality, the selective procedure must:
  * under the masked regime (quality hidden) → ABSTAIN (validated in test_validation);
  * under the FULL regime (quality observed) → COMMIT a config that is truly
    feasible AND minimum-sufficient (the cheapest feasible config, zero regret);
  * when blind, the VoI ranking must point at the blocking axis so that "measuring"
    it un-blocks a correct commit, where a random axis does not.
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver import Phi, make_query
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import Component, Config, ConfigComponent, Source
from prudent_ai.substrate.orm import Observation as ObsORM
from prudent_ai.validation.baselines import SelectiveRule
from prudent_ai.validation.harness import MaskAndPredict, MaskedSubstrate


def _i(session, model, **kw):
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed(sub: Substrate) -> None:
    """tau='gt': (cost, quality) cheap=(1.0,0.50), mid=(5.0,0.80), dear=(9.0,0.95)."""
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


_KAPPA = ("H",)
_PHI = Phi.POINT


def _query():
    # quality>=0.8 → cheap(0.50) fails; mid(0.80) & dear(0.95) feasible; min-cost = mid.
    return make_query("gt", [("quality", ">=", 0.8)], label="q-bound")


# ---- (1) COMMIT-branch validity ----

def test_commit_branch_feasible_and_min_sufficient():
    """Full evidence → selective COMMITs the cheapest feasible config (mid)."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = _query()
    rec = right_size(sub, q, _KAPPA, _PHI, ALL_AXES)
    mp = MaskAndPredict(sub, kappa=_KAPPA, phi=_PHI)

    assert rec.action is Action.COMMIT
    assert rec.committed_config == "mid"            # cheapest feasible, not 'dear'
    assert mp.true_feasible(q, rec.committed_config)  # feasible against GT
    # minimum-sufficient: committed cost == oracle min-cost feasible cost (zero regret)
    assert mp._true_val("mid", "cost") == mp.oracle_cost(q)
    sub.close()


def test_commit_branch_dual_abstains_when_blind():
    """The SAME slice forces ABSTAIN when the binding axis (quality) is masked."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = _query()
    masked = MaskedSubstrate(sub, "quality")
    rec = right_size(masked, q, _KAPPA, _PHI, ALL_AXES - {"quality"})
    assert rec.action is Action.ABSTAIN
    assert "quality" in rec.blocking_axes
    sub.close()


# ---- (2) VoI: pick beats random ----

def test_voi_pick_unblocks_commit_random_does_not():
    """Measuring the VoI-pick (quality) un-blocks a correct commit; cost does not."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = _query()
    masked = MaskedSubstrate(sub, "quality")
    visible = ALL_AXES - {"quality"}
    rec = right_size(masked, q, _KAPPA, _PHI, visible)
    assert rec.action is Action.ABSTAIN
    assert rec.acquire_next == "quality"            # VoI points at the blocking axis

    sel = SelectiveRule()
    mp = MaskAndPredict(sub, kappa=_KAPPA, phi=_PHI)
    # measure VoI-pick (quality) → un-mask → selective commits a feasible config
    top_committed, top_ok = ValidationRunner._commit_correct(
        mp, q, sel, sub, ALL_AXES, _KAPPA, _PHI
    )
    assert top_committed and top_ok
    # measure a random non-blocking axis (cost) → quality stays hidden → abstain
    rand_committed, rand_ok = ValidationRunner._commit_correct(
        mp, q, sel, masked, visible, _KAPPA, _PHI
    )
    assert not rand_committed and not rand_ok
    sub.close()


# ---- significance helper ----

def test_voi_significance_one_sided_binomial():
    pairs = [(True, False)] * 9 + [(False, False)]  # 9 discordant for VoI, 1 tie
    sig = ValidationRunner._voi_significance(pairs)
    assert sig["n"] == 10
    assert sig["mcnemar_b"] == 9 and sig["mcnemar_c"] == 0
    assert sig["topvoi_commit_correct"] == 9
    assert sig["binom_p_one_sided"] < 0.05
    assert sig["significant"] is True
