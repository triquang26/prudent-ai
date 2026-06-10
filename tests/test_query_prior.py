"""Tests for the ZenML empirical query-prior taxonomy (C8-critical artifact).

The tag→axis mapping carries the real-traffic decidability claim, so its behaviour
is pinned here:
  test_governance_from_regulatory_tag / _from_industry — governance binds via tag OR industry.
  test_reviewer_burden_from_hitl — human_in_the_loop ⇒ reviewer_burden.
  test_latency_and_cost_tags — latency/cost engineering tags bind their axes.
  test_quality_always_binds — every derived query carries a quality floor.
  test_throughput_energy_never_fabricated — these are NEVER bound from tags (C1).
  test_archetype_mapping — application tag → substrate τ.
  test_drop_tag_removes_axis — drop-one sensitivity hook actually drops the axis.
  test_determinism — deriving twice is identical.
"""

from __future__ import annotations

from prudent_ai.queries.query_prior import (
    TAG_TO_AXIS,
    build_query_prior,
    derive_query,
)


def _row(app="", tech="", industry="Tech"):
    return {
        "application_tags": app,
        "techniques_tags": tech,
        "industry": industry,
        "title": "case",
    }


def test_governance_from_regulatory_tag():
    dq = derive_query(_row(app="chatbot,regulatory_compliance"))
    assert "governance" in dq.binding_axes


def test_governance_from_industry():
    dq = derive_query(_row(app="chatbot", industry="Healthcare"))
    assert "governance" in dq.binding_axes


def test_reviewer_burden_from_hitl():
    dq = derive_query(_row(app="chatbot", tech="human_in_the_loop"))
    assert "reviewer_burden" in dq.binding_axes


def test_latency_and_cost_tags():
    dq = derive_query(_row(app="chatbot", tech="latency_optimization,cost_optimization"))
    assert {"latency_p95", "cost"} <= dq.binding_axes


def test_quality_always_binds():
    dq = derive_query(_row(app="chatbot"))
    assert "quality" in dq.binding_axes


def test_throughput_energy_never_fabricated():
    """No tag in the taxonomy maps to throughput or energy (C1: never fabricate)."""
    assert "throughput" not in TAG_TO_AXIS.values()
    assert "energy" not in TAG_TO_AXIS.values()
    # Even a row loaded with tags must not bind throughput/energy.
    dq = derive_query(_row(
        app="chatbot,realtime_application,high_stakes_application",
        tech="latency_optimization,cost_optimization,human_in_the_loop",
        industry="Finance",
    ))
    assert "throughput" not in dq.binding_axes
    assert "energy" not in dq.binding_axes


def test_archetype_mapping():
    assert derive_query(_row(app="code_generation")).tau == "function-calling"
    assert derive_query(_row(app="question_answering")).tau == "general-qa"
    assert derive_query(_row(app="realtime_application")).tau == "inference-serving"
    # unmapped application tag → default general-qa
    assert derive_query(_row(app="some_unknown_tag")).tau == "general-qa"


def test_drop_tag_removes_axis():
    full = derive_query(_row(app="chatbot", tech="human_in_the_loop"))
    dropped = derive_query(_row(app="chatbot", tech="human_in_the_loop"),
                           drop_tag="human_in_the_loop")
    assert "reviewer_burden" in full.binding_axes
    assert "reviewer_burden" not in dropped.binding_axes


def test_determinism():
    rows = [_row(app="chatbot,code_generation", tech="latency_optimization"),
            _row(app="question_answering", industry="Legal")]
    p1 = build_query_prior(rows)
    p2 = build_query_prior(rows)
    assert [d.binding_axes for d in p1.derived] == [d.binding_axes for d in p2.derived]
    assert p1.tau_distribution() == p2.tau_distribution()
