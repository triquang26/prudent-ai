"""MedHELM loader — clinical / medical LLM benchmark data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_COMPONENTS = [
    ("cmp-med-gpt4o",   "GPT-4o",           "llm", "OpenAI",    "gpt-4o",          None, "proprietary", 0),
    ("cmp-med-gpt4t",   "GPT-4-turbo",      "llm", "OpenAI",    "gpt-4-turbo",     None, "proprietary", 0),
    ("cmp-med-c35s",    "Claude-3.5-Sonnet","llm", "Anthropic", "claude-3-5-sonnet",None, "proprietary", 0),
    ("cmp-med-meditron","Meditron-70B",      "llm", "EPFL",      "meditron-70b",    70.0, "llama2",      1),
    ("cmp-med-clinical","ClinicalCamel-70B", "llm", "Univ-TX",  "clinicalcamel-70b",70.0,"llama2",      1),
    ("cmp-med-biomed",  "BioMedLM",          "llm", "Stanford",  "biomedlm-v2",      2.7, "CC-BY-NC-4.0",1),
    ("cmp-med-gem15p",  "Gemini-1.5-Pro",   "llm", "Google",    "gemini-1.5-pro",  None, "proprietary", 0),
    ("cmp-med-l3-70b",  "Llama-3-70B",      "llm", "Meta",      "llama-3-70b",     70.0, "llama3",      1),
]

_COMPOSITIONS = [
    ("comp-med-gpt4o-sum",    "MedHELM/GPT-4o/summarization",      "bare_llm", "summarization"),
    ("comp-med-gpt4t-sum",    "MedHELM/GPT-4-turbo/summarization", "bare_llm", "summarization"),
    ("comp-med-c35s-sum",     "MedHELM/Claude-3.5-Sonnet/summary", "bare_llm", "summarization"),
    ("comp-med-meditron-sum", "MedHELM/Meditron-70B/summarization","bare_llm", "summarization"),
    ("comp-med-gpt4o-qa",     "MedHELM/GPT-4o/clinical-QA",       "bare_llm", "question_answering"),
    ("comp-med-c35s-qa",      "MedHELM/Claude-3.5-Sonnet/QA",     "bare_llm", "question_answering"),
    ("comp-med-meditron-qa",  "MedHELM/Meditron-70B/QA",          "bare_llm", "question_answering"),
    ("comp-med-clinical-qa",  "MedHELM/ClinicalCamel-70B/QA",     "bare_llm", "question_answering"),
    ("comp-med-gem15p-qa",    "MedHELM/Gemini-1.5-Pro/QA",        "bare_llm", "question_answering"),
    ("comp-med-l3-70b-qa",    "MedHELM/Llama-3-70B/QA",           "bare_llm", "question_answering"),
    ("comp-med-gpt4o-rag-sum","MedHELM/GPT-4o+RAG/summarization", "rag",      "summarization"),
    ("comp-med-c35s-rag-qa",  "MedHELM/Claude-3.5+RAG/QA",       "rag",      "question_answering"),
]

# (comp_id, cmp_id, task, hw, quality, lat_ms, cost, notes)
_RUNS = [
    ("comp-med-gpt4o-sum",    "cmp-med-gpt4o",    "summarization",   "unknown", 0.712, 1120.0, 0.0150, "MedHELM ROUGE-L clinical notes"),
    ("comp-med-gpt4t-sum",    "cmp-med-gpt4t",    "summarization",   "unknown", 0.698, 1340.0, 0.0140, "MedHELM GPT-4-turbo summary"),
    ("comp-med-c35s-sum",     "cmp-med-c35s",     "summarization",   "unknown", 0.702, 980.0,  0.0120, "MedHELM Claude-3.5 summary"),
    ("comp-med-meditron-sum", "cmp-med-meditron", "summarization",   "A100",    0.675, 780.0,  0.0008, "Meditron-70B — clinical summary"),
    ("comp-med-gpt4o-qa",     "cmp-med-gpt4o",    "question_answering","unknown",0.845,1100.0, 0.0150, "MedHELM clinical-QA accuracy"),
    ("comp-med-c35s-qa",      "cmp-med-c35s",     "question_answering","unknown",0.831, 960.0, 0.0120, "Claude-3.5 clinical-QA"),
    ("comp-med-meditron-qa",  "cmp-med-meditron", "question_answering","A100",   0.798, 760.0, 0.0008, "Meditron-70B clinical-QA"),
    ("comp-med-clinical-qa",  "cmp-med-clinical", "question_answering","A100",   0.782, 775.0, 0.0008, "ClinicalCamel-70B QA"),
    ("comp-med-gem15p-qa",    "cmp-med-gem15p",   "question_answering","unknown",0.820, 310.0, 0.0070, "Gemini-1.5-Pro QA"),
    ("comp-med-l3-70b-qa",    "cmp-med-l3-70b",   "question_answering","A100",   0.775, 180.0, 0.0008, "Llama-3-70B QA"),
    ("comp-med-gpt4o-rag-sum","cmp-med-gpt4o",    "summarization",   "unknown", 0.748, 1250.0, 0.0158, "GPT-4o + RAG medical summary"),
    ("comp-med-c35s-rag-qa",  "cmp-med-c35s",     "question_answering","unknown",0.865, 1100.0,0.0128, "Claude-3.5 + RAG clinical QA (best)"),
]


class MedHELMLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        self._ins_source(con, "src-medhelm", "benchmark",
            "MedHELM — Medical Holistic Evaluation of Language Models",
            "https://crfm.stanford.edu/helm/medhelm/", "2024-04-01", "Apache-2.0")
        for ev in [
            ("ev-med-rouge",  "src-medhelm", "metric", "ROUGE-L on clinical note summarization", "Table 2", "2024-04-01"),
            ("ev-med-acc",    "src-medhelm", "metric", "Accuracy on medical QA benchmarks", "Table 3", "2024-04-01"),
            ("ev-med-safety", "src-medhelm", "metric", "Safety rate on medical advice generation", "Table 5", "2024-04-01"),
        ]:
            self._ins_ev(con, *ev)
        for row in _COMPONENTS:
            self._ins_comp_item(con, *row)
        for comp_id, name, pattern, task in _COMPOSITIONS:
            ev = "ev-med-rouge" if "sum" in comp_id else "ev-med-acc"
            self._ins_composition(con, comp_id, name, pattern, task, ev, f"MedHELM — {name}")
        count = 0
        for comp_id, cmp_id, task, hw, quality, lat, cost, notes in _RUNS:
            ev = "ev-med-rouge" if "sum" in comp_id else "ev-med-acc"
            run_id = f"med-{comp_id.replace('comp-med-', '')}"
            qm = "rouge_l" if "sum" in comp_id else "accuracy"
            self._ins_run(con, run_id, comp_id, cmp_id, ev, task, hw, quality, lat, cost, None, None,
                          qm, "medhelm", notes)
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
