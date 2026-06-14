"""MLEnergy Survey loader — energy-per-token data for hosted and open LLMs."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_COMPONENTS = [
    ("cmp-mle-gpt4o",    "GPT-4o",             "llm", "OpenAI",    "gpt-4o",            None, "proprietary", 0),
    ("cmp-mle-gpt35",    "GPT-3.5-turbo",      "llm", "OpenAI",    "gpt-3.5-turbo",     None, "proprietary", 0),
    ("cmp-mle-c3h",      "Claude-3-Haiku",     "llm", "Anthropic", "claude-3-haiku",    None, "proprietary", 0),
    ("cmp-mle-gem15f",   "Gemini-1.5-Flash",   "llm", "Google",    "gemini-1.5-flash",  None, "proprietary", 0),
    ("cmp-mle-l3-70b",   "Llama-3-70B",        "llm", "Meta",      "llama-3-70b",       70.0, "llama3",      1),
    ("cmp-mle-l3-8b",    "Llama-3-8B",         "llm", "Meta",      "llama-3-8b",         8.0, "llama3",      1),
    ("cmp-mle-mixtral",  "Mixtral-8x7B",       "llm", "Mistral",   "mixtral-8x7b",      46.7, "Apache-2.0",  1),
    ("cmp-mle-phi3",     "Phi-3-mini-4k",      "llm", "Microsoft", "phi-3-mini-4k",      3.8, "MIT",         1),
    ("cmp-mle-falcon7b", "Falcon-7B",          "llm", "TII",       "falcon-7b",          7.0, "Apache-2.0",  1),
    ("cmp-mle-gemma7b",  "Gemma-7B",           "llm", "Google",    "gemma-7b",           7.0, "gemma",       1),
]

# (comp_id, name, pattern, task)
_COMPOSITIONS = [
    ("comp-mle-gpt4o",   "MLEnergy/GPT-4o",           "bare_llm", "text_generation"),
    ("comp-mle-gpt35",   "MLEnergy/GPT-3.5-turbo",    "bare_llm", "text_generation"),
    ("comp-mle-c3h",     "MLEnergy/Claude-3-Haiku",   "bare_llm", "text_generation"),
    ("comp-mle-gem15f",  "MLEnergy/Gemini-1.5-Flash", "bare_llm", "text_generation"),
    ("comp-mle-l3-70b",  "MLEnergy/Llama-3-70B",      "bare_llm", "text_generation"),
    ("comp-mle-l3-8b",   "MLEnergy/Llama-3-8B",       "bare_llm", "text_generation"),
    ("comp-mle-mixtral", "MLEnergy/Mixtral-8x7B",     "bare_llm", "text_generation"),
    ("comp-mle-phi3",    "MLEnergy/Phi-3-mini-4k",    "bare_llm", "text_generation"),
    ("comp-mle-falcon7b","MLEnergy/Falcon-7B",         "bare_llm", "text_generation"),
    ("comp-mle-gemma7b", "MLEnergy/Gemma-7B",         "bare_llm", "text_generation"),
]

# (cmp_id, hw, quality, lat_ms, cost, energy_J, mem_GB)
_RUNS = [
    ("cmp-mle-gpt4o",    "unknown", 0.910, 320.0, 0.0150, None,   None),
    ("cmp-mle-gpt35",    "unknown", 0.820, 78.0,  0.0015, None,   None),
    ("cmp-mle-c3h",      "unknown", 0.755, 92.0,  0.0010, None,   None),
    ("cmp-mle-gem15f",   "unknown", 0.770, 95.0,  0.0010, None,   None),
    ("cmp-mle-l3-70b",   "A100",    0.810, 180.0, 0.0008, 130.0,  40.0),
    ("cmp-mle-l3-8b",    "A100",    0.720, 80.0,  0.0004,  35.0,   8.0),
    ("cmp-mle-mixtral",  "A100",    0.800, 160.0, 0.0006, 110.0,  24.0),
    ("cmp-mle-phi3",     "T4",      0.680, 145.0, 0.0002,  20.0,   4.0),
    ("cmp-mle-falcon7b", "A100",    0.680, 170.0, 0.0004,  55.0,   7.0),
    ("cmp-mle-gemma7b",  "T4",      0.690, 145.0, 0.0003,  45.0,   7.0),
]


class MLEnergyLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        self._ins_source(con, "src-mlenergy", "benchmark",
            "MLEnergy Survey — energy efficiency of LLM inference",
            "https://ml.energy", "2024-05-01", "CC-BY-4.0")
        for ev in [
            ("ev-mle-energy", "src-mlenergy", "metric", "Energy J per 1k tokens on reference hardware", "Table 2", "2024-05-01"),
            ("ev-mle-perf",   "src-mlenergy", "metric", "Quality score across standard tasks", "Table 3", "2024-05-01"),
        ]:
            self._ins_ev(con, *ev)
        for cid, name, ctype, provider, ver, params, lic, ow in _COMPONENTS:
            self._ins_comp_item(con, cid, name, ctype, provider, ver, params, lic, ow)
        for comp_id, name, pattern, task in _COMPOSITIONS:
            self._ins_composition(con, comp_id, name, pattern, task, "ev-mle-energy",
                                  f"MLEnergy survey — {name}")
        count = 0
        for (comp_id, _, pattern, _task), (cmp_id, hw, quality, lat, cost, energy, mem) in zip(_COMPOSITIONS, _RUNS):
            run_id = f"mle-{cmp_id.replace('cmp-mle-', '')}"
            self._ins_run(con, run_id, comp_id, cmp_id, "ev-mle-energy",
                          "text_generation", hw, quality, lat, cost, energy, mem,
                          "accuracy", "mlenergy", f"MLEnergy — {cmp_id}")
            count += 1
        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = MLEnergyLoader(db).load()
    print(f"MLEnergy: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
