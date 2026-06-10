"""Tests for the data-source registry + the extraction scaffolding (plug-in seams)."""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.extraction import (
    ExtractedObservation,
    ExtractionContext,
    SourceRecord,
    cohen_kappa,
    extraction_error_rate,
    load,
)
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import Config
from prudent_ai.substrate.registry import SOURCE_REGISTRY, registry_by_name

# ---- data-source registry ----

def test_registry_lists_all_sources():
    names = {s.name for s in SOURCE_REGISTRY}
    # the original structured sources + the HELM-family suites (auto-registered)
    assert {"helm_lite", "bfcl", "mlperf", "mlenergy", "routerbench", "medhelm"} <= names
    assert {"mmlu", "classic", "reasoning", "safety", "torr"} <= names  # helm suites
    assert len(names) >= 18  # toward the master-plan §13 12–20 source target
    # every spec is self-describing and seedable
    for s in SOURCE_REGISTRY:
        assert s.tau and s.axes and s.confidence in {"H", "M", "L"}
        assert callable(s.seed_fn)


def test_registry_by_name_roundtrip():
    by = registry_by_name()
    assert by["routerbench"].confidence == "H"
    assert "cost" in by["bfcl"].axes


# ---- extraction loader ----

def _seeded_config_substrate():
    sub = Substrate(":memory:")
    sub._session.execute(sqlite_insert(Config).values(id="cfg-x", tau="t").on_conflict_do_nothing())
    sub._session.commit()
    return sub


def test_loader_inserts_known_config_skips_unknown():
    sub = _seeded_config_substrate()
    src = SourceRecord("paper-1", "paper_reported", "Doe 2026", "v1")
    obs = [
        ExtractedObservation("cfg-x", "quality", 0.8, None, "M", "paper-1",
                             annotator="ann1", context=ExtractionContext(dataset="d")),
        ExtractedObservation("cfg-UNKNOWN", "quality", 0.9, None, "M", "paper-1"),
        ExtractedObservation("cfg-x", "cost", None, None, "M", "paper-1"),  # no value
    ]
    rep = load(sub, src, obs)
    sub.close()
    assert rep.inserted == 1
    assert rep.skipped_unknown_config == 1
    assert rep.skipped_no_value == 1


def test_loaded_obs_is_readable_via_interface():
    sub = _seeded_config_substrate()
    src = SourceRecord("paper-2", "paper_reported", "c", "v")
    load(sub, src, [ExtractedObservation("cfg-x", "quality", 0.77, None, "H", "paper-2")])
    cell = sub.cell("cfg-x", "quality")
    sub.close()
    assert len(cell) == 1
    assert cell[0].value_num == 0.77
    assert cell[0].confidence == "H"


# ---- extraction QC: kappa + error rate ----

def _obs(cfg, axis, val, ann):
    return ExtractedObservation(cfg, axis, val, None, "M", "src", annotator=ann)


def test_cohen_kappa_perfect_agreement():
    a = [_obs("c1", "quality", 0.8, "A"), _obs("c2", "cost", 1.0, "A")]
    b = [_obs("c1", "quality", 0.8, "B"), _obs("c2", "cost", 1.0, "B")]
    r = cohen_kappa(a, b)
    assert r.n_shared_cells == 2
    assert r.observed_agreement == 1.0
    assert r.kappa == 1.0


def test_cohen_kappa_partial_disagreement():
    a = [_obs("c1", "quality", 0.8, "A"), _obs("c2", "quality", 0.5, "A")]
    b = [_obs("c1", "quality", 0.8, "B"), _obs("c2", "quality", 0.9, "B")]
    r = cohen_kappa(a, b)
    assert r.n_shared_cells == 2
    assert r.observed_agreement == 0.5
    assert r.kappa < 1.0


def test_extraction_error_rate():
    gold = [_obs("c1", "quality", 0.8, "G"), _obs("c2", "cost", 2.0, "G")]
    pred = [_obs("c1", "quality", 0.8, "P"), _obs("c2", "cost", 9.9, "P")]  # 2nd wrong
    r = extraction_error_rate(pred, gold)
    assert r.n_gold == 2
    assert r.n_wrong == 1
    assert r.overall_error_rate == 0.5
    assert r.per_axis["cost"] == 1.0
    assert r.per_axis["quality"] == 0.0
