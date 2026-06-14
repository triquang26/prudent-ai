"""HAL (Holistic Agent Leaderboard) loader — agent benchmark data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_COMPONENTS = [
    ("cmp-hal-gpt4o",    "GPT-4o",            "llm",   "OpenAI",    "gpt-4o",            None, "proprietary", 0),
    ("cmp-hal-gpt4t",    "GPT-4-turbo",       "llm",   "OpenAI",    "gpt-4-turbo",       None, "proprietary", 0),
    ("cmp-hal-c35s",     "Claude-3.5-Sonnet", "llm",   "Anthropic", "claude-3-5-sonnet", None, "proprietary", 0),
    ("cmp-hal-gem15p",   "Gemini-1.5-Pro",    "llm",   "Google",    "gemini-1.5-pro",    None, "proprietary", 0),
    ("cmp-hal-l3-70b",   "Llama-3-70B",       "llm",   "Meta",      "llama-3-70b",       70.0, "llama3",      1),
    ("cmp-hal-l3-8b",    "Llama-3-8B",        "llm",   "Meta",      "llama-3-8b",         8.0, "llama3",      1),
    ("cmp-hal-code-tool","code_executor",      "tool",  "sandbox",   "sandbox-v1",        None, "MIT",         1),
    ("cmp-hal-search",   "web_search",         "tool",  "various",   "search-v1",         None, "MIT",         1),
]

_COMPOSITIONS = [
    ("comp-hal-gpt4o-single",   "HAL/GPT-4o/single-agent",         "single_agent", "general_agent"),
    ("comp-hal-gpt4t-single",   "HAL/GPT-4-turbo/single-agent",    "single_agent", "general_agent"),
    ("comp-hal-c35s-single",    "HAL/Claude-3.5-Sonnet/single",    "single_agent", "general_agent"),
    ("comp-hal-gem15p-single",  "HAL/Gemini-1.5-Pro/single",       "single_agent", "general_agent"),
    ("comp-hal-l3-70b-single",  "HAL/Llama-3-70B/single",          "single_agent", "general_agent"),
    ("comp-hal-gpt4o-multi",    "HAL/GPT-4o/multi-agent",          "multi_agent",  "collaborative_agent"),
    ("comp-hal-c35s-multi",     "HAL/Claude-3.5-Sonnet/multi",     "multi_agent",  "collaborative_agent"),
    ("comp-hal-l3-70b-multi",   "HAL/Llama-3-70B/multi-agent",     "multi_agent",  "collaborative_agent"),
    ("comp-hal-gpt4o-tool",     "HAL/GPT-4o/tool-agent",           "tool_agent",   "code_agent"),
    ("comp-hal-c35s-tool",      "HAL/Claude-3.5-Sonnet/tool",      "tool_agent",   "code_agent"),
    ("comp-hal-l3-8b-single",   "HAL/Llama-3-8B/single-agent",     "single_agent", "general_agent"),
    ("comp-hal-gem15p-multi",   "HAL/Gemini-1.5-Pro/multi-agent",  "multi_agent",  "collaborative_agent"),
]

# (comp_id, cmp_id, hw, quality, lat_ms, cost, notes)
_RUNS = [
    ("comp-hal-gpt4o-single",  "cmp-hal-gpt4o",  "unknown", 0.620, 5200.0,  0.085, "HAL single-agent score — GPT-4o"),
    ("comp-hal-gpt4t-single",  "cmp-hal-gpt4t",  "unknown", 0.598, 5800.0,  0.095, "HAL single-agent — GPT-4-turbo"),
    ("comp-hal-c35s-single",   "cmp-hal-c35s",   "unknown", 0.638, 4800.0,  0.075, "HAL single-agent — Claude-3.5-Sonnet (best single)"),
    ("comp-hal-gem15p-single", "cmp-hal-gem15p", "unknown", 0.590, 5100.0,  0.065, "HAL single-agent — Gemini-1.5-Pro"),
    ("comp-hal-l3-70b-single", "cmp-hal-l3-70b", "A100",    0.542, 6200.0,  0.010, "HAL single-agent — Llama-3-70B self-hosted"),
    ("comp-hal-gpt4o-multi",   "cmp-hal-gpt4o",  "unknown", 0.695, 18000.0, 0.250, "HAL multi-agent — GPT-4o (orchestrator + workers)"),
    ("comp-hal-c35s-multi",    "cmp-hal-c35s",   "unknown", 0.712, 17500.0, 0.220, "HAL multi-agent — Claude-3.5-Sonnet (best multi)"),
    ("comp-hal-l3-70b-multi",  "cmp-hal-l3-70b", "A100",    0.621, 22000.0, 0.030, "HAL multi-agent — Llama-3-70B"),
    ("comp-hal-gpt4o-tool",    "cmp-hal-gpt4o",  "unknown", 0.710, 8500.0,  0.120, "HAL tool-agent — GPT-4o with code executor"),
    ("comp-hal-c35s-tool",     "cmp-hal-c35s",   "unknown", 0.725, 7800.0,  0.095, "HAL tool-agent — Claude-3.5-Sonnet (best tool)"),
    ("comp-hal-l3-8b-single",  "cmp-hal-l3-8b",  "A100",    0.445, 5500.0,  0.004, "HAL single-agent — Llama-3-8B (budget)"),
    ("comp-hal-gem15p-multi",  "cmp-hal-gem15p", "unknown", 0.668, 16000.0, 0.190, "HAL multi-agent — Gemini-1.5-Pro"),
]


class HALLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        self._ins_source(con, "src-hal", "benchmark",
            "HAL — Holistic Agent Leaderboard",
            "https://hal-leaderboard.github.io/", "2024-06-01", "Apache-2.0")
        for ev in [
            ("ev-hal-success", "src-hal", "metric", "Task success rate across HAL benchmark tasks", "Table 1", "2024-06-01"),
            ("ev-hal-cost",    "src-hal", "metric", "Total cost per task completion",               "Table 2", "2024-06-01"),
            ("ev-hal-steps",   "src-hal", "metric", "Number of tool-use steps to completion",       "Table 3", "2024-06-01"),
        ]:
            self._ins_ev(con, *ev)
        for row in _COMPONENTS:
            self._ins_comp_item(con, *row)
        for comp_id, name, pattern, task in _COMPOSITIONS:
            self._ins_composition(con, comp_id, name, pattern, task, "ev-hal-success",
                                  f"HAL — {name}")
        count = 0
        for comp_id, cmp_id, hw, quality, lat, cost, notes in _RUNS:
            run_id = f"hal-{comp_id.replace('comp-hal-', '')}"
            self._ins_run(con, run_id, comp_id, cmp_id, "ev-hal-success",
                          "agent_task", hw, quality, lat, cost, None, None,
                          "success_rate", "hal", notes)
            count += 1
        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = HALLoader(db).load()
    print(f"HAL: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
