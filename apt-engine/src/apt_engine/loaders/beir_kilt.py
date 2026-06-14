"""BEIR + KILT loader — RAG retrieval benchmark data."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

_LLM_COMPONENTS = [
    ("cmp-bk-gpt4o",   "GPT-4o",            "llm",       "OpenAI",    "gpt-4o",          None, "proprietary", 0),
    ("cmp-bk-gpt35",   "GPT-3.5-turbo",     "llm",       "OpenAI",    "gpt-3.5-turbo",   None, "proprietary", 0),
    ("cmp-bk-l3-70b",  "Llama-3-70B",       "llm",       "Meta",      "llama-3-70b",     70.0, "llama3",      1),
    ("cmp-bk-l3-8b",   "Llama-3-8B",        "llm",       "Meta",      "llama-3-8b",       8.0, "llama3",      1),
]
_RETRIEVER_COMPONENTS = [
    ("cmp-bk-bm25",    "BM25",              "retriever", "Elastic",   "bm25-v1",         None, "Apache-2.0",  1),
    ("cmp-bk-dpr",     "DPR",               "retriever", "Facebook",  "dpr-v1",          None, "CC-BY-NC-4.0",1),
    ("cmp-bk-contriever","Contriever",       "retriever", "Meta",      "contriever-v1",   None, "CC-BY-NC-4.0",1),
    ("cmp-bk-e5large", "E5-large-v2",       "retriever", "Microsoft", "e5-large-v2",     None, "MIT",         1),
    ("cmp-bk-cohere",  "Cohere-rerank-v3",  "reranker",  "Cohere",    "rerank-3",        None, "proprietary", 0),
]

_COMPOSITIONS = [
    ("comp-bk-bm25-gpt4o",       "BEIR/BM25+GPT-4o",         "rag", "question_answering"),
    ("comp-bk-bm25-gpt35",       "BEIR/BM25+GPT-3.5",        "rag", "question_answering"),
    ("comp-bk-dpr-gpt4o",        "BEIR/DPR+GPT-4o",          "rag", "question_answering"),
    ("comp-bk-dpr-gpt35",        "BEIR/DPR+GPT-3.5",         "rag", "question_answering"),
    ("comp-bk-contriever-gpt4o", "BEIR/Contriever+GPT-4o",   "rag", "question_answering"),
    ("comp-bk-contriever-l3-70b","BEIR/Contriever+Llama3-70B","rag", "question_answering"),
    ("comp-bk-e5-gpt4o",         "BEIR/E5+GPT-4o",           "rag", "question_answering"),
    ("comp-bk-e5-rerank-gpt4o",  "BEIR/E5+Rerank+GPT-4o",   "rag_reasoning", "question_answering"),
    ("comp-bk-kilt-dpr-gpt35",   "KILT/DPR+GPT-3.5",        "rag", "knowledge_intensive"),
    ("comp-bk-kilt-e5-gpt4o",    "KILT/E5+GPT-4o",          "rag", "knowledge_intensive"),
    ("comp-bk-kilt-contriever-l3","KILT/Contriever+Llama3",  "rag", "knowledge_intensive"),
    ("comp-bk-bm25-l3-8b",       "BEIR/BM25+Llama3-8B",     "rag", "question_answering"),
]

# (comp_id, llm_id, ret_id, quality, lat_ms, cost, notes)
_RUNS = [
    ("comp-bk-bm25-gpt4o",       "cmp-bk-gpt4o",  "cmp-bk-bm25",       0.820, 420.0, 0.0155, "BEIR avg nDCG@10 — BM25 + GPT-4o"),
    ("comp-bk-bm25-gpt35",       "cmp-bk-gpt35",  "cmp-bk-bm25",       0.768, 165.0, 0.0018, "BEIR avg nDCG@10 — BM25 + GPT-3.5"),
    ("comp-bk-dpr-gpt4o",        "cmp-bk-gpt4o",  "cmp-bk-dpr",        0.810, 450.0, 0.0155, "BEIR — DPR + GPT-4o"),
    ("comp-bk-dpr-gpt35",        "cmp-bk-gpt35",  "cmp-bk-dpr",        0.755, 195.0, 0.0018, "BEIR — DPR + GPT-3.5"),
    ("comp-bk-contriever-gpt4o", "cmp-bk-gpt4o",  "cmp-bk-contriever", 0.835, 440.0, 0.0155, "BEIR — Contriever + GPT-4o"),
    ("comp-bk-contriever-l3-70b","cmp-bk-l3-70b", "cmp-bk-contriever", 0.798, 280.0, 0.0010, "BEIR — Contriever + Llama3-70B"),
    ("comp-bk-e5-gpt4o",         "cmp-bk-gpt4o",  "cmp-bk-e5large",    0.845, 435.0, 0.0155, "BEIR — E5-large + GPT-4o"),
    ("comp-bk-e5-rerank-gpt4o",  "cmp-bk-gpt4o",  "cmp-bk-cohere",     0.872, 620.0, 0.0200, "BEIR — E5+Rerank+GPT-4o (best pipeline)"),
    ("comp-bk-kilt-dpr-gpt35",   "cmp-bk-gpt35",  "cmp-bk-dpr",        0.748, 190.0, 0.0018, "KILT — DPR + GPT-3.5"),
    ("comp-bk-kilt-e5-gpt4o",    "cmp-bk-gpt4o",  "cmp-bk-e5large",    0.838, 440.0, 0.0155, "KILT — E5 + GPT-4o"),
    ("comp-bk-kilt-contriever-l3","cmp-bk-l3-70b","cmp-bk-contriever", 0.790, 275.0, 0.0010, "KILT — Contriever + Llama3-70B"),
    ("comp-bk-bm25-l3-8b",       "cmp-bk-l3-8b",  "cmp-bk-bm25",       0.710, 145.0, 0.0006, "BEIR — BM25 + Llama3-8B (budget)"),
]


class BEIRKILTLoader(BaseLoader):
    def _load(self, con: sqlite3.Connection) -> int:
        for src in [
            ("src-beir", "benchmark", "BEIR: Heterogeneous Retrieval Benchmark",
             "https://github.com/beir-cellar/beir", "2024-01-01", "Apache-2.0"),
            ("src-kilt", "benchmark", "KILT: Knowledge-Intensive Language Tasks",
             "https://ai.facebook.com/tools/kilt/", "2024-01-01", "CC-BY-NC-4.0"),
        ]:
            self._ins_source(con, *src)

        for ev in [
            ("ev-beir-ndcg", "src-beir", "metric", "nDCG@10 averaged over 18 BEIR datasets", "Table 1", "2024-01-01"),
            ("ev-kilt-acc",  "src-kilt", "metric", "Exact match accuracy across KILT tasks", "Table 2", "2024-01-01"),
        ]:
            self._ins_ev(con, *ev)

        for row in _LLM_COMPONENTS + _RETRIEVER_COMPONENTS:
            self._ins_comp_item(con, *row)

        for comp_id, name, pattern, task in _COMPOSITIONS:
            src_ev = "ev-kilt-acc" if "kilt" in comp_id else "ev-beir-ndcg"
            self._ins_composition(con, comp_id, name, pattern, task, src_ev,
                                  f"RAG pipeline — {name}")

        count = 0
        for comp_id, llm_id, ret_id, quality, lat, cost, notes in _RUNS:
            src_ev = "ev-kilt-acc" if "kilt" in comp_id else "ev-beir-ndcg"
            run_id = f"bk-{comp_id.replace('comp-bk-', '')}"
            self._ins_run(con, run_id, comp_id, llm_id, src_ev,
                          "question_answering", "unknown", quality, lat, cost, None, None,
                          "ndcg_at_10", "beir_kilt", notes)
            count += 1
        return count


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = BEIRKILTLoader(db).load()
    print(f"BEIR+KILT: loaded {n} benchmark_run rows")


if __name__ == "__main__":
    main()
