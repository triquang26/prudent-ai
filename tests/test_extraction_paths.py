"""Path 1 (L-quarantine) + Path 2 (cross-extractor consensus → M) tests.

These prove the two annotator-free enrichment paths behave exactly as designed:

  Path 1 — AxCell/MOLE extractors emit at confidence L; the default policy κ={H,M}
           excludes them, so a hard-claim decision is byte-identical with and without
           the auto-extracted rows; only κ={H,M,L} surfaces them. Never-invent: bad
           rows are dropped, not guessed.
  Path 2 — `cross_agreement` promotes a cell to M only where two independent
           extractors agree within tolerance; disagreements and single-extractor
           cells are not promoted. The promotion is M (never H).
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.extraction import (
    AxCellExtractor,
    MOLEExtractor,
    SourceRecord,
    cross_agreement,
    load,
    per_axis_promotion,
)
from prudent_ai.solver import Phi, make_query
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import Component, Config, ConfigComponent, Source
from prudent_ai.substrate.orm import Observation as ObsORM


def _i(session, model, **kw):
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed(sub: Substrate) -> None:
    """tau='gt' with H-confidence (cost, quality): cheap=(1,.50) dear=(9,.95)."""
    s = sub._session
    _i(s, Source, evidence_id="gt", source_type="benchmark", citation="gt",
       snapshot_version="1")
    for cid, cost, q in [("cheap", 1.0, 0.50), ("dear", 9.0, 0.95)]:
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gt")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")
        for axis, val, oid in (("cost", cost, f"{cid}-c"), ("quality", q, f"{cid}-q")):
            _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
               value_cat=None, confidence="H", evidence_id="gt", hardware_tier="hw",
               dataset="d", split="test", decoding_cfg="x", obs_date="2026")
    s.commit()


# --------------------------------------------------------------------------
# Path 1 — extractors emit L, never invent
# --------------------------------------------------------------------------

def test_axcell_emits_L_and_maps_metrics():
    rows = [
        {"config_id": "cheap", "metric": "accuracy", "value": 0.55, "dataset": "mmlu"},
        {"config_id": "cheap", "metric": "latency_p95", "value": 2.1},
    ]
    obs = AxCellExtractor().extract("paperX", rows)
    assert len(obs) == 2
    assert {o.axis for o in obs} == {"quality", "latency_p95"}
    assert all(o.confidence == "L" for o in obs)         # Path 1 quarantine
    assert all(o.annotator == "axcell" for o in obs)


def test_axcell_never_invents():
    rows = [
        {"config_id": "cheap", "metric": "accuracy", "value": None},      # no value
        {"config_id": "cheap", "metric": "perplexity", "value": 12.0},    # unmapped
        {"config_id": "cheap", "metric": "accuracy", "value": 1.7},       # off-[0,1]
        {"metric": "accuracy", "value": 0.8},                              # no config
        {"config_id": "cheap", "metric": "accuracy", "value": 0.81},      # the only good one
    ]
    obs = AxCellExtractor().extract("paperX", rows)
    assert len(obs) == 1
    assert obs[0].value_num == 0.81


def test_mole_schema_projection_emits_L():
    recs = [{"config_id": "dear", "fields": {"quality": 0.93, "cost": 8.0, "foo": 1}}]
    obs = MOLEExtractor().extract("paperY", recs)
    assert {o.axis for o in obs} == {"quality", "cost"}   # 'foo' unmapped → dropped
    assert all(o.confidence == "L" and o.annotator == "mole" for o in obs)


def test_L_rows_do_not_change_a_hard_claim():
    """The load-bearing guarantee: auto-extracted L evidence cannot move a κ={H,M}
    decision. We make gt evidence say 'cheap is infeasible (q .50 < .8)' so the
    procedure COMMITs 'dear'; then we inject an L row claiming cheap has quality .99.
    Under default κ={H,M} the decision is unchanged; under κ={H,M,L} the L row is
    visible (proving it was ingested, just quarantined)."""
    sub = Substrate(":memory:")
    _seed(sub)
    q = make_query("gt", [("quality", ">=", 0.8)], label="q")

    rec_before = right_size(sub, q, ("H", "M"), Phi.POINT, ALL_AXES)
    assert rec_before.action is Action.COMMIT
    assert rec_before.committed_config == "dear"

    # Inject an auto-extracted L row that would flip the decision IF trusted.
    ax = AxCellExtractor()
    obs = ax.extract("attack", [{"config_id": "cheap", "metric": "accuracy", "value": 0.99}])
    rep = load(sub, ax.source_record("attack"), obs)
    assert rep.inserted == 1                               # it really landed in the DB

    rec_after = right_size(sub, q, ("H", "M"), Phi.POINT, ALL_AXES)
    assert rec_after.action is Action.COMMIT
    assert rec_after.committed_config == "dear"            # κ={H,M}: unchanged

    # κ={H,M,L} actually sees the L evidence (cheap now also looks feasible).
    cheap_vals_HM = [o for o in sub.cell("cheap", "quality") if o.confidence in ("H", "M")]
    cheap_vals_HML = [o for o in sub.cell("cheap", "quality") if o.confidence in ("H", "M", "L")]
    assert len(cheap_vals_HML) == len(cheap_vals_HM) + 1
    sub.close()


# --------------------------------------------------------------------------
# Path 2 — cross-extractor consensus → M
# --------------------------------------------------------------------------

def test_cross_agreement_promotes_only_concurring_cells():
    a = AxCellExtractor().extract("p", [
        {"config_id": "cheap", "metric": "accuracy", "value": 0.80},   # agree
        {"config_id": "dear", "metric": "accuracy", "value": 0.90},    # disagree
        {"config_id": "cheap", "metric": "cost", "value": 1.0},        # a-only
    ])
    b = MOLEExtractor().extract("p", [
        {"config_id": "cheap", "fields": {"quality": 0.81}},           # agree (~0.80)
        {"config_id": "dear", "fields": {"quality": 0.60}},            # disagree
        {"config_id": "dear", "fields": {"cost": 8.0}},                # b-only
    ])
    promoted, report = cross_agreement(a, b, rel_tol=0.05)

    assert report.n_shared_cells == 2                      # (cheap,quality) (dear,quality)
    assert report.n_agreed == 1                            # only (cheap, quality)
    assert report.n_disagreed == 1
    assert len(promoted) == 1
    p = promoted[0]
    assert (p.config_id, p.axis) == ("cheap", "quality")
    assert p.confidence == "M"                             # consensus → M, never H
    assert p.annotator == "consensus"
    assert abs(p.value_num - 0.805) < 1e-9                 # mean of 0.80 and 0.81
    assert per_axis_promotion(promoted) == {"quality": 1}


def _consensus_source() -> SourceRecord:
    return SourceRecord(
        evidence_id="consensus", source_type="paper_reported",
        citation="AxCell∩MOLE consensus (machine IAA proxy)", snapshot_version="c-1",
    )


def test_consensus_M_participates_but_stays_below_H():
    """A consensus M row is visible to κ={H,M} (unlike L), but excluded from κ={H}."""
    a = AxCellExtractor().extract(
        "p", [{"config_id": "cheap", "metric": "accuracy", "value": 0.80}]
    )
    b = MOLEExtractor().extract("p", [{"config_id": "cheap", "fields": {"quality": 0.80}}])
    promoted, _ = cross_agreement(a, b)
    assert promoted and promoted[0].confidence == "M"

    sub = Substrate(":memory:")
    _seed(sub)
    load(sub, _consensus_source(), promoted)
    cell = sub.cell("cheap", "quality")
    assert any(o.confidence == "M" and o.evidence_id == "consensus" for o in cell)
    assert all(o.confidence != "H" or o.evidence_id == "gt" for o in cell)  # no fake H
    sub.close()
