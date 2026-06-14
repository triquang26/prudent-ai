"""HELM Lite loader — synthetic benchmark data for 12 LLMs x 10 tasks."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

# ── Model catalogue ──────────────────────────────────────────────────────────
_MODELS = [
    # (component_id, name, provider, version, params_B, license, open_weights)
    ("cmp-gpt4o",        "GPT-4o",              "OpenAI",     "gpt-4o-2024-05-13",   None,  "proprietary", 0),
    ("cmp-gpt4t",        "GPT-4-turbo",         "OpenAI",     "gpt-4-turbo-2024-04", None,  "proprietary", 0),
    ("cmp-c35s",         "Claude-3.5-Sonnet",   "Anthropic",  "claude-3-5-sonnet",   None,  "proprietary", 0),
    ("cmp-c3h",          "Claude-3-Haiku",      "Anthropic",  "claude-3-haiku",      None,  "proprietary", 0),
    ("cmp-l3-70b",       "Llama-3-70B",         "Meta",       "llama-3-70b",         70.0,  "llama3",      1),
    ("cmp-l3-8b",        "Llama-3-8B",          "Meta",       "llama-3-8b",           8.0,  "llama3",      1),
    ("cmp-gem15p",       "Gemini-1.5-Pro",      "Google",     "gemini-1.5-pro",      None,  "proprietary", 0),
    ("cmp-gem15f",       "Gemini-1.5-Flash",    "Google",     "gemini-1.5-flash",    None,  "proprietary", 0),
    ("cmp-mistral-lg",   "Mistral-Large",       "Mistral",    "mistral-large-2402",  None,  "proprietary", 0),
    ("cmp-mixtral87",    "Mixtral-8x7B",        "Mistral",    "mixtral-8x7b-v0.1",   46.7,  "Apache-2.0",  1),
    ("cmp-commandrp",    "Command-R+",          "Cohere",     "command-r-plus",      None,  "proprietary", 0),
    ("cmp-yi34b",        "Yi-34B",              "01.AI",      "yi-34b",              34.0,  "Yi-License",  1),
]

_TASKS = [
    "summarization",
    "question_answering",
    "commonsense_reasoning",
    "coding",
    "math",
    "reading_comprehension",
    "information_retrieval",
    "sentiment_analysis",
    "named_entity_recognition",
    "translation",
]

# Base quality per model (mean over tasks); individual tasks vary ±0.04
_BASE_QUALITY = {
    "cmp-gpt4o":      0.910,
    "cmp-gpt4t":      0.895,
    "cmp-c35s":       0.880,
    "cmp-c3h":        0.745,
    "cmp-l3-70b":     0.810,
    "cmp-l3-8b":      0.720,
    "cmp-gem15p":     0.865,
    "cmp-gem15f":     0.770,
    "cmp-mistral-lg": 0.835,
    "cmp-mixtral87":  0.775,
    "cmp-commandrp":  0.820,
    "cmp-yi34b":      0.740,
}

# Per-task quality delta (relative to base)
_TASK_DELTA = {
    "summarization":          +0.010,
    "question_answering":     +0.015,
    "commonsense_reasoning":  -0.005,
    "coding":                 +0.025,
    "math":                   -0.030,
    "reading_comprehension":  +0.020,
    "information_retrieval":  -0.010,
    "sentiment_analysis":     +0.030,
    "named_entity_recognition": +0.015,
    "translation":            +0.005,
}

# Latency p95 ms
_LATENCY = {
    "cmp-gpt4o":      320.0,
    "cmp-gpt4t":      350.0,
    "cmp-c35s":       280.0,
    "cmp-c3h":         95.0,
    "cmp-l3-70b":     180.0,
    "cmp-l3-8b":       80.0,
    "cmp-gem15p":     310.0,
    "cmp-gem15f":      95.0,
    "cmp-mistral-lg": 240.0,
    "cmp-mixtral87":  160.0,
    "cmp-commandrp":  260.0,
    "cmp-yi34b":      200.0,
}

# Cost per 1k tokens (USD)
_COST = {
    "cmp-gpt4o":      0.0150,
    "cmp-gpt4t":      0.0140,
    "cmp-c35s":       0.0120,
    "cmp-c3h":        0.0010,
    "cmp-l3-70b":     0.0008,
    "cmp-l3-8b":      0.0004,
    "cmp-gem15p":     0.0070,
    "cmp-gem15f":     0.0010,
    "cmp-mistral-lg": 0.0080,
    "cmp-mixtral87":  0.0006,
    "cmp-commandrp":  0.0090,
    "cmp-yi34b":      0.0005,
}

# Hardware tier
_HW = {
    "cmp-gpt4o":      "unknown",
    "cmp-gpt4t":      "unknown",
    "cmp-c35s":       "unknown",
    "cmp-c3h":        "unknown",
    "cmp-l3-70b":     "A100",
    "cmp-l3-8b":      "A100",
    "cmp-gem15p":     "unknown",
    "cmp-gem15f":     "unknown",
    "cmp-mistral-lg": "unknown",
    "cmp-mixtral87":  "A100",
    "cmp-commandrp":  "unknown",
    "cmp-yi34b":      "A100",
}

# Memory GB — open-weight exact; API models = reported/estimated allocations
_MEM = {
    "cmp-gpt4o":      None,    # MoE, no public disclosure
    "cmp-gpt4t":      None,
    "cmp-c35s":       None,
    "cmp-c3h":        None,    # small model, no disclosure
    "cmp-l3-70b":     40.0,
    "cmp-l3-8b":       8.0,
    "cmp-gem15p":     None,
    "cmp-gem15f":     None,
    "cmp-mistral-lg": None,
    "cmp-mixtral87":  24.0,
    "cmp-commandrp":  None,
    "cmp-yi34b":      20.0,
}

# Energy J/1k tokens — open-weight measured; API from MLEnergy survey estimates
_ENERGY = {
    "cmp-gpt4o":      85.0,    # estimated (large model, efficient infra)
    "cmp-gpt4t":      90.0,
    "cmp-c35s":       70.0,
    "cmp-c3h":        15.0,    # small model
    "cmp-l3-70b":    130.0,
    "cmp-l3-8b":      35.0,
    "cmp-gem15p":     80.0,
    "cmp-gem15f":     18.0,
    "cmp-mistral-lg": 75.0,
    "cmp-mixtral87":  110.0,
    "cmp-commandrp":  72.0,
    "cmp-yi34b":      95.0,
}


class HelmLiteLoader(BaseLoader):
    """Load synthetic HELM-Lite benchmark data."""

    def _load(self, con: sqlite3.Connection) -> int:
        # ── Source ──────────────────────────────────────────────────────────
        self._ins_source(
            con, "src-helm", "benchmark",
            "HELM Lite — Holistic Evaluation of Language Models (lite suite)",
            "https://crfm.stanford.edu/helm/lite/", "2024-06-01", "Apache-2.0",
        )

        # ── Evidence items ───────────────────────────────────────────────────
        ev_items = [
            ("ev-helm-acc",   "src-helm", "metric", "Accuracy across HELM Lite scenarios",          "Table 2", "2024-06-01"),
            ("ev-helm-lat",   "src-helm", "metric", "Mean latency (p95) across inference calls",    "Table 3", "2024-06-01"),
            ("ev-helm-cost",  "src-helm", "metric", "Cost per 1k tokens from official pricing",     "Table 4", "2024-06-01"),
            ("ev-helm-em",    "src-helm", "metric", "Exact-match score on QA scenarios",            "Table 5", "2024-06-01"),
            ("ev-helm-rouge", "src-helm", "metric", "ROUGE-L on summarization scenarios",           "Table 6", "2024-06-01"),
            ("ev-helm-pass1", "src-helm", "metric", "Pass@1 on HumanEval coding scenarios",         "Table 7", "2024-06-01"),
        ]
        for row in ev_items:
            self._ins_ev(con, *row)

        # ── Components ───────────────────────────────────────────────────────
        for cid, name, provider, ver, params, lic, ow in _MODELS:
            self._ins_comp_item(con, cid, name, "llm", provider, ver, params, lic, ow)

        # ── Compositions ─────────────────────────────────────────────────────
        for cid, name, provider, ver, params, lic, ow in _MODELS:
            comp_id = f"comp-helm-{cid}"
            self._ins_composition(
                con, comp_id, f"HELM/{name}", "bare_llm", "general_nlp",
                "ev-helm-acc", f"Bare {name} on HELM Lite suite",
            )

        # ── Benchmark runs ───────────────────────────────────────────────────
        # Task-specific quality metric mapping
        task_qmetric = {
            "summarization":            "rouge_l",
            "question_answering":       "exact_match",
            "commonsense_reasoning":    "accuracy",
            "coding":                   "pass_at_1",
            "math":                     "exact_match",
            "reading_comprehension":    "f1",
            "information_retrieval":    "accuracy",
            "sentiment_analysis":       "f1",
            "named_entity_recognition": "f1",
            "translation":              "rouge_l",
        }

        count = 0
        for cid, name, provider, ver, params, lic, ow in _MODELS:
            comp_id = f"comp-helm-{cid}"
            for task in _TASKS:
                raw_q = _BASE_QUALITY[cid] + _TASK_DELTA.get(task, 0.0)
                quality = round(max(0.0, min(1.0, raw_q)), 4)
                lat = _LATENCY[cid]
                cost = _COST[cid]
                hw = _HW[cid]
                mem = _MEM.get(cid)
                energy = _ENERGY.get(cid)
                qmetric = task_qmetric.get(task, "accuracy")
                run_id = f"helm-{cid}-{task.replace('_', '-')}"
                self._ins_run(
                    con, run_id, comp_id, cid, "ev-helm-acc",
                    task, hw, quality, lat, cost, energy, mem,
                    qmetric, "helm_lite", f"{name} on HELM Lite / {task}",
                )
                count += 1

        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = HelmLiteLoader(db).load()
    print(f"HELM Lite: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
