"""RouterBench loader — LLM router quality/latency/cost benchmark data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

# ── Component catalogue ─────────────────────────────────────────────────────
# (component_id, name, component_type, provider, version, params_B, license, open_weights)
_COMPONENTS = [
    ("cmp-rb-frugalgpt",  "FrugalGPT",           "llm",   "Stanford",   "frugalgpt-v1",    None, "research",    0),
    ("cmp-rb-llmrouter",  "LLM-Router",           "llm",   "Martian",    "llm-router-v2",   None, "proprietary", 0),
    ("cmp-rb-routellm",   "RouteLLM",             "llm",   "LMSys",      "routellm-v1",     None, "Apache-2.0",  0),
    ("cmp-rb-gpt4o",      "GPT-4o",               "llm",   "OpenAI",     "gpt-4o-2024-05",  None, "proprietary", 0),
    ("cmp-rb-gpt35",      "GPT-3.5-turbo",        "llm",   "OpenAI",     "gpt-3.5-turbo",   None, "proprietary", 0),
    ("cmp-rb-c35h",       "Claude-3.5-Haiku",     "llm",   "Anthropic",  "claude-3-5-haiku",None, "proprietary", 0),
    ("cmp-rb-l3-70b",     "Llama-3-70B",          "llm",   "Meta",       "llama-3-70b",     70.0, "llama3",      1),
    ("cmp-rb-l3-8b",      "Llama-3-8B",           "llm",   "Meta",       "llama-3-8b",       8.0, "llama3",      1),
    ("cmp-rb-mixtral87",  "Mixtral-8x7B",         "llm",   "Mistral",    "mixtral-8x7b",    46.7, "Apache-2.0",  1),
    ("cmp-rb-cascadellm", "CascadeLLM",           "llm",   "Research",   "cascade-llm-v1",  None, "research",    0),
]

# Compositions: routing strategy × difficulty tier
# (comp_id, name, pattern, task_archetype)
_COMPOSITIONS = [
    ("comp-rb-frugal-routing",  "FrugalGPT/routing",        "bare_llm", "routing"),
    ("comp-rb-frugal-cls",      "FrugalGPT/classification", "bare_llm", "classification"),
    ("comp-rb-martian-routing",  "LLM-Router/routing",      "bare_llm", "routing"),
    ("comp-rb-routellm-routing", "RouteLLM/routing",        "bare_llm", "routing"),
    ("comp-rb-routellm-gen",     "RouteLLM/general",        "bare_llm", "general"),
    ("comp-rb-cascade-routing",  "CascadeLLM/routing",      "bare_llm", "routing"),
    ("comp-rb-cascade-cls",      "CascadeLLM/classification","bare_llm","classification"),
    ("comp-rb-gpt4o-baseline",   "GPT-4o/baseline",         "bare_llm", "general"),
    ("comp-rb-gpt35-baseline",   "GPT-3.5/baseline",        "bare_llm", "general"),
    ("comp-rb-l3-70b-baseline",  "Llama-3-70B/baseline",    "bare_llm", "general"),
    ("comp-rb-l3-8b-baseline",   "Llama-3-8B/baseline",     "bare_llm", "general"),
    ("comp-rb-mixtral-baseline", "Mixtral-8x7B/baseline",   "bare_llm", "general"),
    ("comp-rb-hybrid-easy",      "Hybrid/easy-queries",     "bare_llm", "routing"),
    ("comp-rb-hybrid-hard",      "Hybrid/hard-queries",     "bare_llm", "routing"),
    ("comp-rb-hybrid-mixed",     "Hybrid/mixed-queries",    "bare_llm", "general"),
]

# Run definitions: (comp_id, cmp_id, task, hw, quality, latency_ms, cost, notes)
_RUNS = [
    # FrugalGPT variants
    ("rbench-frugal-rt-easy",   "comp-rb-frugal-routing",   "cmp-rb-frugalgpt",  "routing",        "unknown", 0.880, 110.0, 0.0028, "Easy queries routed to cheap model"),
    ("rbench-frugal-rt-hard",   "comp-rb-frugal-routing",   "cmp-rb-frugalgpt",  "routing",        "unknown", 0.860, 340.0, 0.0095, "Hard queries escalated to GPT-4o"),
    ("rbench-frugal-cls-easy",  "comp-rb-frugal-cls",       "cmp-rb-frugalgpt",  "classification", "unknown", 0.920, 85.0,  0.0018, "Classification — easy tier"),
    ("rbench-frugal-cls-hard",  "comp-rb-frugal-cls",       "cmp-rb-frugalgpt",  "classification", "unknown", 0.870, 280.0, 0.0110, "Classification — hard tier"),
    # LLM-Router (Martian)
    ("rbench-martian-rt-easy",  "comp-rb-martian-routing",  "cmp-rb-llmrouter",  "routing",        "unknown", 0.894, 95.0,  0.0022, "Martian router — easy workload"),
    ("rbench-martian-rt-hard",  "comp-rb-martian-routing",  "cmp-rb-llmrouter",  "routing",        "unknown", 0.873, 390.0, 0.0120, "Martian router — hard workload"),
    ("rbench-martian-rt-mixed", "comp-rb-martian-routing",  "cmp-rb-llmrouter",  "general",        "unknown", 0.883, 210.0, 0.0065, "Martian router — mixed workload"),
    # RouteLLM
    ("rbench-routellm-rt-easy", "comp-rb-routellm-routing", "cmp-rb-routellm",   "routing",        "unknown", 0.876, 102.0, 0.0030, "RouteLLM — easy percentile"),
    ("rbench-routellm-rt-hard", "comp-rb-routellm-routing", "cmp-rb-routellm",   "routing",        "unknown", 0.854, 410.0, 0.0130, "RouteLLM — hard percentile"),
    ("rbench-routellm-gen",     "comp-rb-routellm-gen",     "cmp-rb-routellm",   "general",        "unknown", 0.831, 195.0, 0.0058, "RouteLLM — general generation"),
    # CascadeLLM
    ("rbench-cascade-rt",       "comp-rb-cascade-routing",  "cmp-rb-cascadellm", "routing",        "unknown", 0.862, 150.0, 0.0042, "CascadeLLM routing"),
    ("rbench-cascade-cls",      "comp-rb-cascade-cls",      "cmp-rb-cascadellm", "classification", "unknown", 0.905, 78.0,  0.0015, "CascadeLLM classification"),
    # GPT-4o baseline (upper bound)
    ("rbench-gpt4o-gen",        "comp-rb-gpt4o-baseline",   "cmp-rb-gpt4o",      "general",        "unknown", 0.940, 320.0, 0.0150, "GPT-4o baseline — full cost"),
    ("rbench-gpt4o-cls",        "comp-rb-gpt4o-baseline",   "cmp-rb-gpt4o",      "classification", "unknown", 0.945, 305.0, 0.0148, "GPT-4o classification baseline"),
    # GPT-3.5 baseline
    ("rbench-gpt35-gen",        "comp-rb-gpt35-baseline",   "cmp-rb-gpt35",      "general",        "unknown", 0.820, 78.0,  0.0015, "GPT-3.5-turbo baseline"),
    ("rbench-gpt35-cls",        "comp-rb-gpt35-baseline",   "cmp-rb-gpt35",      "classification", "unknown", 0.835, 74.0,  0.0014, "GPT-3.5-turbo classification"),
    # Llama-3-70B
    ("rbench-l3-70b-gen",       "comp-rb-l3-70b-baseline",  "cmp-rb-l3-70b",     "general",        "A100",    0.835, 185.0, 0.0008, "Llama-3-70B self-hosted"),
    ("rbench-l3-70b-cls",       "comp-rb-l3-70b-baseline",  "cmp-rb-l3-70b",     "classification", "A100",    0.849, 180.0, 0.0008, "Llama-3-70B classification"),
    # Llama-3-8B
    ("rbench-l3-8b-gen",        "comp-rb-l3-8b-baseline",   "cmp-rb-l3-8b",      "general",        "A100",    0.750, 78.0,  0.0003, "Llama-3-8B self-hosted"),
    ("rbench-l3-8b-cls",        "comp-rb-l3-8b-baseline",   "cmp-rb-l3-8b",      "classification", "A100",    0.762, 75.0,  0.0003, "Llama-3-8B classification"),
    # Mixtral-8x7B
    ("rbench-mixtral-gen",      "comp-rb-mixtral-baseline", "cmp-rb-mixtral87",  "general",        "A100",    0.800, 162.0, 0.0006, "Mixtral-8x7B self-hosted"),
    ("rbench-mixtral-cls",      "comp-rb-mixtral-baseline", "cmp-rb-mixtral87",  "classification", "A100",    0.813, 158.0, 0.0006, "Mixtral-8x7B classification"),
    # Hybrid strategies
    ("rbench-hybrid-easy-rt",   "comp-rb-hybrid-easy",      "cmp-rb-frugalgpt",  "routing",        "unknown", 0.877, 88.0,  0.0020, "Hybrid: cheap model for easy queries"),
    ("rbench-hybrid-hard-rt",   "comp-rb-hybrid-hard",      "cmp-rb-frugalgpt",  "routing",        "unknown", 0.921, 360.0, 0.0140, "Hybrid: GPT-4o for hard queries"),
    ("rbench-hybrid-mixed-gen", "comp-rb-hybrid-mixed",     "cmp-rb-frugalgpt",  "general",        "unknown", 0.895, 185.0, 0.0062, "Hybrid: adaptive routing mixed"),
    # Claude-3.5-Haiku as cheap model
    ("rbench-c35h-cls",         "comp-rb-gpt35-baseline",   "cmp-rb-c35h",       "classification", "unknown", 0.850, 90.0,  0.0010, "Claude-3.5-Haiku classification"),
    ("rbench-c35h-rt",          "comp-rb-routellm-routing", "cmp-rb-c35h",       "routing",        "unknown", 0.838, 87.0,  0.0009, "Claude-3.5-Haiku routing"),
    # Additional coverage
    ("rbench-frugal-rt-v2",     "comp-rb-frugal-routing",   "cmp-rb-frugalgpt",  "general",        "unknown", 0.872, 175.0, 0.0048, "FrugalGPT mixed general workload"),
    ("rbench-cascade-gen",      "comp-rb-cascade-routing",  "cmp-rb-cascadellm", "general",        "unknown", 0.845, 168.0, 0.0045, "CascadeLLM general generation"),
    ("rbench-martian-cls",      "comp-rb-martian-routing",  "cmp-rb-llmrouter",  "classification", "unknown", 0.889, 105.0, 0.0032, "Martian router classification"),
    # Low-cost strategy
    ("rbench-l3-8b-rt",         "comp-rb-l3-8b-baseline",   "cmp-rb-l3-8b",      "routing",        "A100",    0.720, 72.0,  0.0003, "Llama-3-8B routing (cost optimized)"),
    ("rbench-l3-70b-rt",        "comp-rb-l3-70b-baseline",  "cmp-rb-l3-70b",     "routing",        "A100",    0.810, 183.0, 0.0008, "Llama-3-70B routing"),
    ("rbench-routellm-cls",     "comp-rb-routellm-routing", "cmp-rb-routellm",   "classification", "unknown", 0.866, 108.0, 0.0035, "RouteLLM classification"),
    # Budget-constraint test
    ("rbench-frugal-budget",    "comp-rb-frugal-cls",       "cmp-rb-gpt35",      "classification", "unknown", 0.795, 82.0,  0.0014, "FrugalGPT budget-constrained"),
    ("rbench-cascade-budget",   "comp-rb-cascade-cls",      "cmp-rb-l3-8b",      "classification", "A100",    0.739, 74.0,  0.0003, "CascadeLLM budget mode"),
    # Routing accuracy under distribution shift
    ("rbench-frugal-shift",     "comp-rb-frugal-routing",   "cmp-rb-frugalgpt",  "routing",        "unknown", 0.823, 145.0, 0.0052, "FrugalGPT under distribution shift"),
    ("rbench-martian-shift",    "comp-rb-martian-routing",  "cmp-rb-llmrouter",  "routing",        "unknown", 0.841, 155.0, 0.0058, "Martian under distribution shift"),
    ("rbench-routellm-shift",   "comp-rb-routellm-routing", "cmp-rb-routellm",   "routing",        "unknown", 0.816, 160.0, 0.0055, "RouteLLM under distribution shift"),
    # High quality ceiling
    ("rbench-gpt4o-routing",    "comp-rb-gpt4o-baseline",   "cmp-rb-gpt4o",      "routing",        "unknown", 0.948, 315.0, 0.0150, "GPT-4o routing accuracy ceiling"),
    ("rbench-gpt4o-mixed",      "comp-rb-gpt4o-baseline",   "cmp-rb-gpt4o",      "general",        "unknown", 0.937, 322.0, 0.0152, "GPT-4o mixed tasks"),
    # Cost vs quality Pareto
    ("rbench-mixtral-routing",  "comp-rb-mixtral-baseline", "cmp-rb-mixtral87",  "routing",        "A100",    0.785, 160.0, 0.0006, "Mixtral routing — Pareto efficient"),
]


class RouterBenchLoader(BaseLoader):
    """Load synthetic RouterBench data."""

    def _load(self, con: sqlite3.Connection) -> int:
        # ── Source ──────────────────────────────────────────────────────────
        self._ins_source(
            con, "src-rbench", "benchmark",
            "RouterBench — LLM routing strategy evaluation suite",
            "https://github.com/withmartian/routerbench", "2024-07-01",
            "Apache-2.0",
        )

        # ── Evidence items ───────────────────────────────────────────────────
        ev_items = [
            ("ev-rbench-acc",   "src-rbench", "metric", "Routing accuracy across difficulty tiers",       "Table 1", "2024-07-01"),
            ("ev-rbench-lat",   "src-rbench", "metric", "End-to-end latency including routing overhead",   "Table 2", "2024-07-01"),
            ("ev-rbench-cost",  "src-rbench", "metric", "Effective cost per 1k tokens after routing",      "Table 3", "2024-07-01"),
            ("ev-rbench-shift", "src-rbench", "metric", "Routing accuracy under distribution shift",       "Table 4", "2024-07-01"),
        ]
        for row in ev_items:
            self._ins_ev(con, *row)

        # ── Components ───────────────────────────────────────────────────────
        for cid, name, ctype, provider, ver, params, lic, ow in _COMPONENTS:
            self._ins_comp_item(con, cid, name, ctype, provider, ver, params, lic, ow)

        # ── Compositions ─────────────────────────────────────────────────────
        for comp_id, name, pattern, task in _COMPOSITIONS:
            self._ins_composition(
                con, comp_id, name, pattern, task,
                "ev-rbench-acc", f"RouterBench — {name}",
            )

        # ── Benchmark runs ───────────────────────────────────────────────────
        count = 0
        for (run_id, comp_id, cmp_id, task, hw,
             quality, lat, cost, notes) in _RUNS:
            self._ins_run(
                con, run_id, comp_id, cmp_id, "ev-rbench-acc",
                task, hw, quality, lat, cost, None, None,
                "accuracy", "routerbench", notes,
            )
            count += 1

        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = RouterBenchLoader(db).load()
    print(f"RouterBench: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
