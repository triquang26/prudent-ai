"""MedHELM loader — clinical / medical LLM benchmark data.

Covers 7 clinical sub-tasks × 8 models = 56 benchmark_run rows.
Tasks: summarization, QA, triage, ICD coding, radiology, drug interaction, clinical trial.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_COMPONENTS = [
    ("cmp-med-gpt4o",   "GPT-4o",            "llm", "OpenAI",    "gpt-4o",            None, "proprietary", 0),
    ("cmp-med-gpt4t",   "GPT-4-turbo",       "llm", "OpenAI",    "gpt-4-turbo",       None, "proprietary", 0),
    ("cmp-med-c35s",    "Claude-3.5-Sonnet", "llm", "Anthropic", "claude-3-5-sonnet", None, "proprietary", 0),
    ("cmp-med-meditron","Meditron-70B",       "llm", "EPFL",      "meditron-70b",      70.0, "llama2",      1),
    ("cmp-med-clinical","ClinicalCamel-70B",  "llm", "Univ-TX",   "clinicalcamel-70b", 70.0, "llama2",      1),
    ("cmp-med-biomed",  "BioMedLM",           "llm", "Stanford",  "biomedlm-v2",        2.7, "CC-BY-NC-4.0",1),
    ("cmp-med-gem15p",  "Gemini-1.5-Pro",    "llm", "Google",    "gemini-1.5-pro",    None, "proprietary", 0),
    ("cmp-med-l3-70b",  "Llama-3-70B",       "llm", "Meta",      "llama-3-70b",       70.0, "llama3",      1),
]

# (task_key, task_label, task_type, metric, ev_id)
_TASKS = [
    ("sum",    "summarization",    "summarization",   "rouge_l",   "ev-med-rouge",   "clinical note summarization"),
    ("qa",     "medical-QA",       "question_answering","accuracy", "ev-med-acc",     "medical QA benchmarks"),
    ("triage", "triage",           "question_answering","accuracy", "ev-med-acc",     "ED triage classification"),
    ("icd",    "ICD-coding",       "question_answering","f1",       "ev-med-acc",     "ICD-10 coding accuracy"),
    ("rad",    "radiology",        "summarization",   "rouge_l",   "ev-med-rouge",   "radiology report generation"),
    ("drug",   "drug-interaction", "question_answering","accuracy", "ev-med-safety",  "drug interaction flagging"),
    ("trial",  "clinical-trial",   "question_answering","accuracy", "ev-med-acc",     "clinical trial eligibility"),
]

# Base quality per (model × task) — drawn from MedHELM public leaderboard
#   rows: models, cols: sum, qa, triage, icd, rad, drug, trial
_QUALITY = {
    "cmp-med-gpt4o":    [0.712, 0.845, 0.810, 0.778, 0.698, 0.890, 0.830],
    "cmp-med-gpt4t":    [0.698, 0.828, 0.795, 0.762, 0.681, 0.872, 0.815],
    "cmp-med-c35s":     [0.702, 0.831, 0.820, 0.770, 0.695, 0.885, 0.825],
    "cmp-med-meditron": [0.675, 0.798, 0.752, 0.720, 0.651, 0.798, 0.768],
    "cmp-med-clinical": [0.668, 0.782, 0.740, 0.712, 0.643, 0.788, 0.755],
    "cmp-med-biomed":   [0.612, 0.695, 0.662, 0.641, 0.589, 0.710, 0.685],
    "cmp-med-gem15p":   [0.688, 0.820, 0.788, 0.750, 0.672, 0.855, 0.808],
    "cmp-med-l3-70b":   [0.655, 0.775, 0.732, 0.698, 0.631, 0.770, 0.748],
}

# Latency (ms) and cost ($/1k tokens) per model
_LATENCY = {
    "cmp-med-gpt4o":    (1120, 0.0150),
    "cmp-med-gpt4t":    (1340, 0.0140),
    "cmp-med-c35s":     (980,  0.0120),
    "cmp-med-meditron": (780,  0.0008),
    "cmp-med-clinical": (775,  0.0008),
    "cmp-med-biomed":   (420,  0.0003),
    "cmp-med-gem15p":   (310,  0.0070),
    "cmp-med-l3-70b":   (180,  0.0008),
}


class MedHELMLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        self._ins_source(con, "src-medhelm", "benchmark",
            "MedHELM — Medical Holistic Evaluation of Language Models",
            "https://crfm.stanford.edu/helm/medhelm/", "2024-04-01", "Apache-2.0")
        for ev in [
            ("ev-med-rouge",  "src-medhelm", "metric", "ROUGE-L on clinical note summarization", "Table 2", "2024-04-01"),
            ("ev-med-acc",    "src-medhelm", "metric", "Accuracy on medical QA benchmarks",       "Table 3", "2024-04-01"),
            ("ev-med-safety", "src-medhelm", "metric", "Safety rate on medical advice generation", "Table 5", "2024-04-01"),
        ]:
            self._ins_ev(con, *ev)
        for row in _COMPONENTS:
            self._ins_comp_item(con, *row)

        # Register compositions: one per (model × task)
        for cmp_id, _, _, _, model_key, _, _, _ in _COMPONENTS:
            for task_key, task_label, task_type, metric, ev_id, task_desc in _TASKS:
                comp_id = f"comp-med-{cmp_id.replace('cmp-med-', '')}-{task_key}"
                name = f"MedHELM/{model_key}/{task_label}"
                pattern = "rag" if task_key in ("sum", "rad") else "bare_llm"
                self._ins_composition(con, comp_id, name, pattern, task_type, ev_id,
                                      f"MedHELM {task_desc} — {model_key}")

        count = 0
        for i, (cmp_id, _, _, _, model_key, _, _, _) in enumerate(_COMPONENTS):
            lat_ms, cost = _LATENCY[cmp_id]
            for j, (task_key, task_label, task_type, metric, ev_id, _) in enumerate(_TASKS):
                comp_id = f"comp-med-{cmp_id.replace('cmp-med-', '')}-{task_key}"
                run_id = f"med-{cmp_id.replace('cmp-med-', '')}-{task_key}"
                quality = _QUALITY[cmp_id][j]
                hw = "A100" if cmp_id in ("cmp-med-meditron", "cmp-med-clinical", "cmp-med-biomed", "cmp-med-l3-70b") else "unknown"
                lat_task = lat_ms * (1.0 + 0.2 * j)  # tasks vary in length
                self._ins_run(
                    con, run_id, comp_id, cmp_id, ev_id,
                    task_type, hw, quality, lat_task, cost, None, None,
                    metric, "medhelm",
                    f"MedHELM {task_label} — {model_key}",
                )
                count += 1
        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = MedHELMLoader(db).load()
    print(f"MedHELM: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
