"""MLPerf Inference loader — synthetic hardware/latency/energy benchmark data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

# ── Model catalogue ──────────────────────────────────────────────────────────
# (component_id, name, component_type, provider, version, params_B, license, open_weights)
_MODELS = [
    ("cmp-mp-l3-70b",   "Llama-3-70B (MLPerf)",   "llm",   "Meta",     "llama-3-70b-inf",   70.0, "llama3",     1),
    ("cmp-mp-l3-8b",    "Llama-3-8B (MLPerf)",    "llm",   "Meta",     "llama-3-8b-inf",     8.0, "llama3",     1),
    ("cmp-mp-gptj6b",   "GPT-J-6B (MLPerf)",      "llm",   "EleutherAI","gpt-j-6b",          6.0, "Apache-2.0", 1),
    ("cmp-mp-bert",     "BERT-Large (MLPerf)",     "llm",   "Google",   "bert-large-uncased", 0.34,"Apache-2.0", 1),
    ("cmp-mp-resnet50", "ResNet-50 (MLPerf)",      "llm",   "MLCommons","resnet-50-v1.5",     0.026,"Apache-2.0",1),
    ("cmp-mp-gpt4",     "GPT-4 (MLPerf closed)",  "llm",   "OpenAI",   "gpt-4-closed",      None, "proprietary",0),
    ("cmp-mp-mistral7b","Mistral-7B (MLPerf)",     "llm",   "Mistral",  "mistral-7b-v0.1",    7.0, "Apache-2.0", 1),
    ("cmp-mp-falcon7b", "Falcon-7B (MLPerf)",      "llm",   "TII",      "falcon-7b",          7.0, "Apache-2.0", 1),
    # Additional models for broader coverage (MLPerf open submissions v4.0)
    ("cmp-mp-phi3mini", "Phi-3-mini (MLPerf)",     "llm",   "Microsoft","phi-3-mini-4k",      3.8, "MIT",        1),
    ("cmp-mp-gemma7b",  "Gemma-7B (MLPerf)",       "llm",   "Google",   "gemma-7b",           7.0, "gemma",      1),
    ("cmp-mp-qwen7b",   "Qwen-7B (MLPerf)",        "llm",   "Alibaba",  "qwen-7b",            7.0, "Apache-2.0", 1),
    ("cmp-mp-mixtral8x7b","Mixtral-8x7B (MLPerf)", "llm",   "Mistral",  "mixtral-8x7b-v0.1",  46.7,"Apache-2.0",1),
    ("cmp-mp-l2-13b",   "Llama-2-13B (MLPerf)",   "llm",   "Meta",     "llama-2-13b",        13.0, "llama2",    1),
    ("cmp-mp-starcoder2","StarCoder2-15B (MLPerf)","llm",   "BigCode",  "starcoder2-15b",     15.0, "BigCode-RAIL",1),
]

# (composition_id, name, pattern, task_archetype, evidence_id)
_COMPS = [
    ("comp-mp-l3-70b",   "MLPerf/Llama-3-70B",      "bare_llm", "text_generation"),
    ("comp-mp-l3-8b",    "MLPerf/Llama-3-8B",       "bare_llm", "text_generation"),
    ("comp-mp-gptj6b",   "MLPerf/GPT-J-6B",         "bare_llm", "text_generation"),
    ("comp-mp-bert",     "MLPerf/BERT-Large",        "bare_llm", "classification"),
    ("comp-mp-resnet50", "MLPerf/ResNet-50",         "bare_llm", "classification"),
    ("comp-mp-gpt4",     "MLPerf/GPT-4-closed",     "bare_llm", "text_generation"),
    ("comp-mp-mistral7b","MLPerf/Mistral-7B",        "bare_llm", "text_generation"),
    ("comp-mp-falcon7b", "MLPerf/Falcon-7B",         "bare_llm", "text_generation"),
    ("comp-mp-phi3mini", "MLPerf/Phi-3-mini",        "bare_llm", "text_generation"),
    ("comp-mp-gemma7b",  "MLPerf/Gemma-7B",          "bare_llm", "text_generation"),
    ("comp-mp-qwen7b",   "MLPerf/Qwen-7B",           "bare_llm", "text_generation"),
    ("comp-mp-mixtral8x7b","MLPerf/Mixtral-8x7B",   "bare_llm", "text_generation"),
    ("comp-mp-l2-13b",   "MLPerf/Llama-2-13B",       "bare_llm", "text_generation"),
    ("comp-mp-starcoder2","MLPerf/StarCoder2-15B",   "bare_llm", "text_generation"),
]

# Hardware specs: (hw_tier, latency_base_ms, energy_J_per_1k, memory_mult)
_HW_SPECS = {
    "H100":  (95.0,   80.0,  1.0),
    "A100":  (200.0,  120.0, 1.0),
    "V100":  (400.0,  200.0, 1.0),
    "T4":    (800.0,  250.0, 1.0),
}

# Memory GB per model at fp16
_MEM_GB = {
    "cmp-mp-l3-70b":    40.0,
    "cmp-mp-l3-8b":      8.0,
    "cmp-mp-gptj6b":     6.0,
    "cmp-mp-bert":       0.7,
    "cmp-mp-resnet50":   0.1,
    "cmp-mp-gpt4":      None,  # closed
    "cmp-mp-mistral7b":  7.0,
    "cmp-mp-falcon7b":   7.0,
    "cmp-mp-phi3mini":   3.8,
    "cmp-mp-gemma7b":    7.0,
    "cmp-mp-qwen7b":     7.0,
    "cmp-mp-mixtral8x7b":46.7,
    "cmp-mp-l2-13b":    13.0,
    "cmp-mp-starcoder2": 15.0,
}

# Latency scale factor per model (larger models slower)
_LAT_FACTOR = {
    "cmp-mp-l3-70b":    2.20,
    "cmp-mp-l3-8b":     0.70,
    "cmp-mp-gptj6b":    0.65,
    "cmp-mp-bert":      0.12,
    "cmp-mp-resnet50":  0.05,
    "cmp-mp-gpt4":      3.50,
    "cmp-mp-mistral7b": 0.68,
    "cmp-mp-falcon7b":  0.68,
    "cmp-mp-phi3mini":  0.40,
    "cmp-mp-gemma7b":   0.68,
    "cmp-mp-qwen7b":    0.67,
    "cmp-mp-mixtral8x7b":1.50,
    "cmp-mp-l2-13b":    0.88,
    "cmp-mp-starcoder2":0.95,
}

# Energy scale factor per model
_ENERGY_FACTOR = {
    "cmp-mp-l3-70b":    3.50,
    "cmp-mp-l3-8b":     0.65,
    "cmp-mp-gptj6b":    0.60,
    "cmp-mp-bert":      0.10,
    "cmp-mp-resnet50":  0.04,
    "cmp-mp-gpt4":      5.00,
    "cmp-mp-mistral7b": 0.62,
    "cmp-mp-falcon7b":  0.62,
    "cmp-mp-phi3mini":  0.35,
    "cmp-mp-gemma7b":   0.61,
    "cmp-mp-qwen7b":    0.60,
    "cmp-mp-mixtral8x7b":2.10,
    "cmp-mp-l2-13b":    0.80,
    "cmp-mp-starcoder2":0.88,
}

# Quality scores (from external HELM/lm-eval cross-ref, text_generation accuracy)
_QUALITY = {
    "cmp-mp-l3-70b":    0.810,
    "cmp-mp-l3-8b":     0.720,
    "cmp-mp-gptj6b":    0.620,
    "cmp-mp-bert":      0.875,  # fine-tuned classification
    "cmp-mp-resnet50":  0.762,  # ImageNet top-1
    "cmp-mp-gpt4":      0.900,
    "cmp-mp-mistral7b": 0.728,
    "cmp-mp-falcon7b":  0.680,
    "cmp-mp-phi3mini":  0.692,
    "cmp-mp-gemma7b":   0.711,
    "cmp-mp-qwen7b":    0.725,
    "cmp-mp-mixtral8x7b":0.788,
    "cmp-mp-l2-13b":    0.735,
    "cmp-mp-starcoder2":0.748,
}

# Self-hosting cost per 1k tokens (GPU rental, A100 hourly / throughput)
_COST_PER_1K = {
    "cmp-mp-l3-70b":    0.0008,
    "cmp-mp-l3-8b":     0.0002,
    "cmp-mp-gptj6b":    0.0002,
    "cmp-mp-bert":      0.0001,
    "cmp-mp-resnet50":  0.0001,
    "cmp-mp-gpt4":      0.0300,
    "cmp-mp-mistral7b": 0.0002,
    "cmp-mp-falcon7b":  0.0002,
    "cmp-mp-phi3mini":  0.0001,
    "cmp-mp-gemma7b":   0.0002,
    "cmp-mp-qwen7b":    0.0002,
    "cmp-mp-mixtral8x7b":0.0006,
    "cmp-mp-l2-13b":    0.0003,
    "cmp-mp-starcoder2":0.0003,
}


class MLPerfLoader(BaseLoader):
    """Load synthetic MLPerf Inference benchmark data."""

    def _load(self, con: sqlite3.Connection) -> int:
        # ── Source ──────────────────────────────────────────────────────────
        self._ins_source(
            con, "src-mlperf", "benchmark",
            "MLPerf Inference v4.0 — hardware performance benchmark",
            "https://mlcommons.org/benchmarks/inference/", "2024-04-01",
            "Apache-2.0",
        )

        # ── Evidence items ───────────────────────────────────────────────────
        ev_items = [
            ("ev-mlperf-lat",    "src-mlperf", "metric",
             "p99 latency per query (server scenario)",         "Table 1", "2024-04-01"),
            ("ev-mlperf-tput",   "src-mlperf", "metric",
             "Offline throughput (queries/sec)",                "Table 2", "2024-04-01"),
            ("ev-mlperf-energy", "src-mlperf", "metric",
             "Energy consumption J per 1k tokens",             "Table 3", "2024-04-01"),
        ]
        for row in ev_items:
            self._ins_ev(con, *row)

        # ── Components ───────────────────────────────────────────────────────
        for cid, name, ctype, provider, ver, params, lic, ow in _MODELS:
            self._ins_comp_item(con, cid, name, ctype, provider, ver, params, lic, ow)

        # ── Compositions ─────────────────────────────────────────────────────
        for comp_id, name, pattern, task in _COMPS:
            self._ins_composition(
                con, comp_id, name, pattern, task,
                "ev-mlperf-lat", f"MLPerf inference run — {name}",
            )

        # ── Benchmark runs ───────────────────────────────────────────────────
        count = 0
        hw_list = ["H100", "A100", "V100", "T4"]

        for (comp_id, comp_name, pattern, task_arch), (cid, name, ctype, provider, ver, params, lic, ow) in zip(_COMPS, _MODELS):
            for hw in hw_list:
                # Skip T4 for very large models (OOM)
                if hw == "T4" and params and params >= 70.0:
                    continue
                # Skip V100 for 70B (OOM)
                if hw == "V100" and params and params >= 70.0:
                    continue

                base_lat, base_energy, _ = _HW_SPECS[hw]
                lat = round(base_lat * _LAT_FACTOR[cid], 1)
                energy = round(base_energy * _ENERGY_FACTOR[cid], 1)
                mem = _MEM_GB.get(cid)

                quality = _QUALITY.get(cid)
                cost = _COST_PER_1K.get(cid)
                run_id = f"mlperf-{cid.replace('cmp-mp-', '')}-{hw.lower()}"
                self._ins_run(
                    con, run_id, comp_id, cid, "ev-mlperf-lat",
                    task_arch, hw,
                    quality, lat, cost, energy, mem,
                    "accuracy", "mlperf_inference",
                    f"{name} on {hw} — MLPerf Inference v4.0",
                )
                count += 1

        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = MLPerfLoader(db).load()
    print(f"MLPerf: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
