"""Tests for the RouterBench parser (aggregation + mmlu collapse) — no network/pkl."""

from __future__ import annotations

import pandas as pd

from prudent_ai.substrate.routerbench.parser import RouterBenchParser, benchmark_group


def test_benchmark_group_collapses_mmlu():
    assert benchmark_group("mmlu-anatomy") == "mmlu"
    assert benchmark_group("mmlu-college-physics") == "mmlu"
    assert benchmark_group("grade-school-math") == "grade-school-math"
    assert benchmark_group("hellaswag") == "hellaswag"


def _synthetic_df():
    # Two models, two mmlu subtopics (collapse to one) + one other benchmark.
    m1 = "gpt-4-1106-preview"
    m2 = "claude-v2"
    return pd.DataFrame({
        "sample_id": ["a", "b", "c", "d"],
        "eval_name": ["mmlu-anatomy", "mmlu-astronomy", "hellaswag", "hellaswag"],
        m1: [1.0, 0.0, 1.0, 1.0],
        m2: [0.0, 0.0, 1.0, 0.0],
        f"{m1}|total_cost": [0.01, 0.02, 0.03, 0.03],
        f"{m2}|total_cost": [0.005, 0.005, 0.01, 0.01],
    })


def test_parse_aggregates_per_model_benchmark():
    configs = RouterBenchParser().parse(_synthetic_df())
    by_key = {(c.model, c.benchmark): c for c in configs}

    # gpt-4 mmlu: mean(1.0, 0.0)=0.5 quality, mean(0.01,0.02)=0.015 cost, n=2
    g_mmlu = by_key[("gpt-4-1106-preview", "mmlu")]
    assert g_mmlu.quality == 0.5
    assert g_mmlu.cost == 0.015
    assert g_mmlu.n_prompts == 2

    # gpt-4 hellaswag: mean(1,1)=1.0, cost 0.03, n=2
    g_hella = by_key[("gpt-4-1106-preview", "hellaswag")]
    assert g_hella.quality == 1.0
    assert g_hella.n_prompts == 2

    # claude-v2 mmlu: mean(0,0)=0.0
    assert by_key[("claude-v2", "mmlu")].quality == 0.0


def test_provider_inference():
    configs = RouterBenchParser().parse(_synthetic_df())
    prov = {c.model: c.provider for c in configs}
    assert prov["gpt-4-1106-preview"] == "openai"
    assert prov["claude-v2"] == "anthropic"
