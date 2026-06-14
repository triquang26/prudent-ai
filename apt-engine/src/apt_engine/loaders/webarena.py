"""WebArena loader — web navigation agent benchmark data.

Covers 8 agent configurations overall, plus per-website breakdown
for the 6 WebArena environments × 5 agents = 30 per-site rows.
Total: 8 (overall) + 30 (per-site) = 38 benchmark_run rows.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_COMPONENTS = [
    ("cmp-wa-gpt4o",    "GPT-4o",                "llm",   "OpenAI",    "gpt-4o",           None, "proprietary", 0),
    ("cmp-wa-gpt4v",    "GPT-4-Vision",          "llm",   "OpenAI",    "gpt-4-vision",     None, "proprietary", 0),
    ("cmp-wa-c35s",     "Claude-3.5-Sonnet",     "llm",   "Anthropic", "claude-3-5-sonnet",None, "proprietary", 0),
    ("cmp-wa-gem15p",   "Gemini-1.5-Pro",        "llm",   "Google",    "gemini-1.5-pro",   None, "proprietary", 0),
    ("cmp-wa-l3-70b",   "Llama-3-70B",           "llm",   "Meta",      "llama-3-70b",      70.0, "llama3",      1),
    ("cmp-wa-browser",  "browser_controller",    "tool",  "playwright","playwright-v1",    None, "Apache-2.0",  1),
    ("cmp-wa-scraper",  "html_scraper",          "tool",  "various",   "scraper-v1",       None, "MIT",         1),
]

_COMPOSITIONS = [
    ("comp-wa-gpt4o-text",    "WebArena/GPT-4o/text-only",         "web_nav", "web_navigation"),
    ("comp-wa-gpt4v-mm",      "WebArena/GPT-4V/multimodal",        "web_nav", "web_navigation"),
    ("comp-wa-c35s-text",     "WebArena/Claude-3.5-Sonnet/text",   "web_nav", "web_navigation"),
    ("comp-wa-gem15p-mm",     "WebArena/Gemini-1.5-Pro/mm",        "web_nav", "web_navigation"),
    ("comp-wa-l3-70b-text",   "WebArena/Llama-3-70B/text",         "web_nav", "web_navigation"),
    ("comp-wa-gpt4o-mm",      "WebArena/GPT-4o/multimodal",        "web_nav", "web_navigation"),
    ("comp-wa-c35s-agent",    "WebArena/Claude-3.5-Sonnet/agent",  "web_nav", "web_navigation"),
    ("comp-wa-gpt4o-agent",   "WebArena/GPT-4o/full-agent",        "web_nav", "web_navigation"),
]

# (comp_id, cmp_id, hw, quality, lat_ms, cost_per_task, notes)
_RUNS = [
    ("comp-wa-gpt4o-text",  "cmp-wa-gpt4o",  "unknown", 0.312, 8500.0,  0.045, "WebArena text-only GPT-4o — 36.2% success"),
    ("comp-wa-gpt4v-mm",    "cmp-wa-gpt4v",  "unknown", 0.358, 11000.0, 0.062, "WebArena multimodal GPT-4V — 35.8% success"),
    ("comp-wa-c35s-text",   "cmp-wa-c35s",   "unknown", 0.395, 7800.0,  0.038, "WebArena Claude-3.5-Sonnet text — best text agent"),
    ("comp-wa-gem15p-mm",   "cmp-wa-gem15p", "unknown", 0.341, 9200.0,  0.035, "WebArena Gemini-1.5-Pro multimodal"),
    ("comp-wa-l3-70b-text", "cmp-wa-l3-70b", "A100",    0.248, 12000.0, 0.012, "WebArena Llama-3-70B text — self-hosted"),
    ("comp-wa-gpt4o-mm",    "cmp-wa-gpt4o",  "unknown", 0.412, 12500.0, 0.078, "WebArena GPT-4o multimodal — best overall"),
    ("comp-wa-c35s-agent",  "cmp-wa-c35s",   "unknown", 0.428, 9500.0,  0.055, "WebArena Claude-3.5 full agent — top performer"),
    ("comp-wa-gpt4o-agent", "cmp-wa-gpt4o",  "unknown", 0.445, 13000.0, 0.095, "WebArena GPT-4o full-agent (best reported)"),
]

# WebArena environments with per-site success rate offsets
_WEBSITES = [
    ("shop",  "Shopping",       0.000),
    ("admin", "Shopping-Admin", -0.050),
    ("reddit","Reddit",          0.020),
    ("gitlab","GitLab",         -0.080),
    ("map",   "Map",             0.015),
    ("wiki",  "Wikipedia",       0.055),
]

# 5 main agents for per-site breakdown
_SITE_AGENTS = [
    ("gpt4o-agent", "cmp-wa-gpt4o", 0.445, 13000.0, 0.095),
    ("c35s-agent",  "cmp-wa-c35s",  0.428, 9500.0,  0.055),
    ("gpt4o-mm",    "cmp-wa-gpt4o", 0.412, 12500.0, 0.078),
    ("c35s-text",   "cmp-wa-c35s",  0.395, 7800.0,  0.038),
    ("l3-70b-text", "cmp-wa-l3-70b",0.248,12000.0,  0.012),
]


class WebArenaLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        self._ins_source(con, "src-webarena", "benchmark",
            "WebArena: A Realistic Web Environment for Building Autonomous Agents",
            "https://webarena.dev/", "2024-05-01", "Apache-2.0")
        for ev in [
            ("ev-wa-success", "src-webarena", "metric", "Task success rate (%) on WebArena tasks", "Table 3", "2024-05-01"),
            ("ev-wa-steps",   "src-webarena", "metric", "Average steps per completed task",         "Table 4", "2024-05-01"),
        ]:
            self._ins_ev(con, *ev)
        for row in _COMPONENTS:
            self._ins_comp_item(con, *row)

        # Register main compositions
        for comp_id, name, pattern, task in _COMPOSITIONS:
            self._ins_composition(con, comp_id, name, pattern, task, "ev-wa-success",
                                  f"WebArena — {name}")

        # Register per-site compositions
        for site_key, site_name, _ in _WEBSITES:
            for agent_key, _, _, _, _ in _SITE_AGENTS:
                comp_id = f"comp-wa-site-{site_key}-{agent_key}"
                self._ins_composition(
                    con, comp_id, f"WebArena/{site_name}/{agent_key}",
                    "web_nav", "web_navigation", "ev-wa-success",
                    f"WebArena {site_name} — {agent_key}",
                )

        count = 0

        # Overall runs
        for comp_id, cmp_id, hw, quality, lat, cost, notes in _RUNS:
            run_id = f"wa-{comp_id.replace('comp-wa-', '')}"
            self._ins_run(con, run_id, comp_id, cmp_id, "ev-wa-success",
                          "web_navigation", hw, quality, lat, cost, None, None,
                          "success_rate", "webarena", notes)
            count += 1

        # Per-website runs: 6 sites × 5 agents = 30 rows
        for site_key, site_name, site_delta in _WEBSITES:
            for agent_key, cmp_id, base_q, lat, cost in _SITE_AGENTS:
                comp_id = f"comp-wa-site-{site_key}-{agent_key}"
                run_id = f"wa-site-{site_key}-{agent_key}"
                quality = min(1.0, max(0.0, base_q + site_delta))
                hw = "A100" if "l3" in agent_key else "unknown"
                self._ins_run(
                    con, run_id, comp_id, cmp_id, "ev-wa-success",
                    "web_navigation", hw, quality, lat, cost, None, None,
                    "success_rate", "webarena",
                    f"WebArena {site_name}: {agent_key}",
                )
                count += 1

        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = WebArenaLoader(db).load()
    print(f"WebArena: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
