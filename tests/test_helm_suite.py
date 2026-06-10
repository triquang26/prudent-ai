"""Tests for the generalized HELM-suite ingester (parser quality selection)."""

from __future__ import annotations

from prudent_ai.substrate.helm_lite.models import StatEntry
from prudent_ai.substrate.helm_suite.parser import HelmSuiteParser
from prudent_ai.substrate.helm_suite.seeder import SUITES


def _stat(name: str, mean: float) -> StatEntry:
    return StatEntry(name=name, split="test", perturbation=None, count=10,
                     mean=mean, min=0.0, max=1.0, stddev=0.0)


def test_quality_prefers_scenario_accuracy():
    p = HelmSuiteParser()
    stats = [_stat("clear_accuracy", 0.73), _stat("quasi_exact_match", 0.55),
             _stat("inference_runtime", 2.1)]
    score, metric = p.extract_quality("clear", stats)
    assert metric == "clear_accuracy" and score == 0.73


def test_quality_falls_back_to_accuracy_family():
    p = HelmSuiteParser()
    # no {scenario}_accuracy → fall back to quasi_exact_match (an accuracy-family metric)
    stats = [_stat("quasi_exact_match", 0.61), _stat("inference_runtime", 1.0)]
    score, metric = p.extract_quality("med_qa", stats)
    assert metric == "quasi_exact_match" and score == 0.61


def test_quality_skips_infra_metrics():
    p = HelmSuiteParser()
    # only infra metrics present → no quality
    stats = [_stat("num_prompt_tokens", 512.0), _stat("inference_runtime", 1.0)]
    score, metric = p.extract_quality("whatever", stats)
    assert score is None and metric is None


def test_medhelm_suite_registered():
    by = {s.name: s for s in SUITES}
    assert "medhelm" in by
    spec = by["medhelm"]
    assert spec.tau == "medical-qa"
    assert spec.suite_prefix.startswith("medhelm/")
    assert spec.version.startswith("v")
