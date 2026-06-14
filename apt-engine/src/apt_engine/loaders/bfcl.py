"""BFCL loader — Berkeley Function Calling Leaderboard synthetic data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

# ── Component catalogue ─────────────────────────────────────────────────────
# (component_id, name, component_type, provider, version, params_B, license, open_weights)
_COMPONENTS = [
    ("cmp-bfcl-gpt4o",      "GPT-4o",                    "llm",   "OpenAI",    "gpt-4o-2024-05-13",   None, "proprietary", 0),
    ("cmp-bfcl-c35s",       "Claude-3.5-Sonnet",         "llm",   "Anthropic", "claude-3-5-sonnet",    None, "proprietary", 0),
    ("cmp-bfcl-l3-70b",     "Llama-3-70B-Instruct",      "llm",   "Meta",      "llama-3-70b-instruct", 70.0, "llama3",      1),
    ("cmp-bfcl-mistral-lg", "Mistral-Large",             "llm",   "Mistral",   "mistral-large-2402",   None, "proprietary", 0),
    ("cmp-bfcl-gorilla",    "Gorilla-OpenFunctions-v2",  "llm",   "Gorilla",   "gorilla-openfunctions-v2",6.7,"Apache-2.0",  1),
    ("cmp-bfcl-gem15p",     "Gemini-1.5-Pro",            "llm",   "Google",    "gemini-1.5-pro",       None, "proprietary", 0),
    ("cmp-bfcl-gpt4t",      "GPT-4-turbo",               "llm",   "OpenAI",    "gpt-4-turbo-2024-04",  None, "proprietary", 0),
    ("cmp-bfcl-nexusflow",  "NexusRaven-V2-13B",         "llm",   "Nexusflow", "nexusraven-v2-13b",    13.0, "CC-BY-NC-4.0",1),
    ("cmp-bfcl-xlamf",      "xLAM-8x22B-r",             "llm",   "Salesforce","xlam-8x22b-r",         141.0,"Apache-2.0",  1),
    ("cmp-bfcl-c3h",        "Claude-3-Haiku",            "llm",   "Anthropic", "claude-3-haiku",       None, "proprietary", 0),
]

# Compositions: one per model, pattern = tool_agent
_COMPOSITIONS = [
    ("comp-bfcl-gpt4o",      "BFCL/GPT-4o",                   "tool_agent", "function_calling"),
    ("comp-bfcl-c35s",       "BFCL/Claude-3.5-Sonnet",        "tool_agent", "function_calling"),
    ("comp-bfcl-l3-70b",     "BFCL/Llama-3-70B-Instruct",     "tool_agent", "function_calling"),
    ("comp-bfcl-mistral-lg", "BFCL/Mistral-Large",            "tool_agent", "function_calling"),
    ("comp-bfcl-gorilla",    "BFCL/Gorilla-OpenFunctions-v2", "tool_agent", "function_calling"),
    ("comp-bfcl-gem15p",     "BFCL/Gemini-1.5-Pro",          "tool_agent", "function_calling"),
    ("comp-bfcl-gpt4t",      "BFCL/GPT-4-turbo",             "tool_agent", "function_calling"),
    ("comp-bfcl-nexusflow",  "BFCL/NexusRaven-V2-13B",       "tool_agent", "function_calling"),
    ("comp-bfcl-xlamf",      "BFCL/xLAM-8x22B-r",           "tool_agent", "function_calling"),
    ("comp-bfcl-c3h",        "BFCL/Claude-3-Haiku",          "tool_agent", "function_calling"),
]

# Base function-calling accuracy per model
_BASE_ACC = {
    "cmp-bfcl-gpt4o":      0.950,
    "cmp-bfcl-c35s":       0.930,
    "cmp-bfcl-gpt4t":      0.920,
    "cmp-bfcl-gem15p":     0.905,
    "cmp-bfcl-mistral-lg": 0.878,
    "cmp-bfcl-xlamf":      0.860,
    "cmp-bfcl-l3-70b":     0.830,
    "cmp-bfcl-nexusflow":  0.810,
    "cmp-bfcl-gorilla":    0.782,
    "cmp-bfcl-c3h":        0.755,
}

# Latency p95 ms per model
_LATENCY = {
    "cmp-bfcl-gpt4o":      320.0,
    "cmp-bfcl-c35s":       285.0,
    "cmp-bfcl-gpt4t":      355.0,
    "cmp-bfcl-gem15p":     315.0,
    "cmp-bfcl-mistral-lg": 245.0,
    "cmp-bfcl-xlamf":      520.0,
    "cmp-bfcl-l3-70b":     185.0,
    "cmp-bfcl-nexusflow":  420.0,
    "cmp-bfcl-gorilla":    390.0,
    "cmp-bfcl-c3h":         92.0,
}

# Cost per 1k tokens
_COST = {
    "cmp-bfcl-gpt4o":      0.0150,
    "cmp-bfcl-c35s":       0.0120,
    "cmp-bfcl-gpt4t":      0.0140,
    "cmp-bfcl-gem15p":     0.0070,
    "cmp-bfcl-mistral-lg": 0.0080,
    "cmp-bfcl-xlamf":      0.0006,
    "cmp-bfcl-l3-70b":     0.0008,
    "cmp-bfcl-nexusflow":  0.0004,
    "cmp-bfcl-gorilla":    0.0004,
    "cmp-bfcl-c3h":        0.0010,
}

# Hardware tier
_HW = {
    "cmp-bfcl-gpt4o":      "unknown",
    "cmp-bfcl-c35s":       "unknown",
    "cmp-bfcl-gpt4t":      "unknown",
    "cmp-bfcl-gem15p":     "unknown",
    "cmp-bfcl-mistral-lg": "unknown",
    "cmp-bfcl-xlamf":      "A100",
    "cmp-bfcl-l3-70b":     "A100",
    "cmp-bfcl-nexusflow":  "A100",
    "cmp-bfcl-gorilla":    "A100",
    "cmp-bfcl-c3h":        "unknown",
}

# BFCL categories with quality delta vs base
_CATEGORIES = [
    ("simple_function",     +0.025, "Single function, no nesting"),
    ("multiple_function",   -0.015, "Parallel multiple function calls"),
    ("nested_function",     -0.040, "Nested/composed function calls"),
    ("parallel_multiple",   -0.025, "Parallel calls to multiple APIs"),
    ("rest_api",            -0.010, "REST API function calling"),
    ("sql_function",        -0.020, "SQL-style function invocation"),
]


class BFCLLoader(BaseLoader):
    """Load synthetic Berkeley Function Calling Leaderboard data."""

    def _load(self, con: sqlite3.Connection) -> int:
        # ── Source ──────────────────────────────────────────────────────────
        self._ins_source(
            con, "src-bfcl", "benchmark",
            "Berkeley Function Calling Leaderboard (BFCL) v3",
            "https://gorilla.cs.berkeley.edu/leaderboard.html", "2024-08-01",
            "Apache-2.0",
        )

        # ── Evidence items ───────────────────────────────────────────────────
        ev_items = [
            ("ev-bfcl-acc",      "src-bfcl", "metric", "Overall function-calling accuracy",            "Table 1", "2024-08-01"),
            ("ev-bfcl-simple",   "src-bfcl", "metric", "Simple function call accuracy",                "Table 2", "2024-08-01"),
            ("ev-bfcl-multi",    "src-bfcl", "metric", "Multiple function call accuracy",              "Table 3", "2024-08-01"),
            ("ev-bfcl-nested",   "src-bfcl", "metric", "Nested function call accuracy",               "Table 4", "2024-08-01"),
            ("ev-bfcl-rest",     "src-bfcl", "metric", "REST API function calling accuracy",          "Table 5", "2024-08-01"),
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
                "ev-bfcl-acc", f"BFCL evaluation — {name}",
            )

        # ── Benchmark runs ───────────────────────────────────────────────────
        count = 0
        comp_map = {c[0]: c for c in _COMPOSITIONS}
        cmp_map  = {c[0]: c for c in _COMPONENTS}

        for comp_id, comp_name, pattern, task_arch in _COMPOSITIONS:
            # Derive cmp_id by matching comp_id suffix to component
            cmp_id = comp_id.replace("comp-bfcl-", "cmp-bfcl-")
            base_acc = _BASE_ACC[cmp_id]
            lat = _LATENCY[cmp_id]
            cost = _COST[cmp_id]
            hw = _HW[cmp_id]

            for cat_slug, delta, notes_suffix in _CATEGORIES:
                quality = round(max(0.0, min(1.0, base_acc + delta)), 4)
                run_id = f"bfcl-{cmp_id.replace('cmp-bfcl-', '')}-{cat_slug.replace('_', '-')}"
                cat_ev = {
                    "simple_function":   "ev-bfcl-simple",
                    "multiple_function": "ev-bfcl-multi",
                    "nested_function":   "ev-bfcl-nested",
                    "parallel_multiple": "ev-bfcl-multi",
                    "rest_api":          "ev-bfcl-rest",
                    "sql_function":      "ev-bfcl-acc",
                }.get(cat_slug, "ev-bfcl-acc")

                self._ins_run(
                    con, run_id, comp_id, cmp_id, cat_ev,
                    cat_slug, hw, quality, lat, cost, None, None,
                    "accuracy", "bfcl", f"{comp_name} — {notes_suffix}",
                )
                count += 1

        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = BFCLLoader(db).load()
    print(f"BFCL: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
