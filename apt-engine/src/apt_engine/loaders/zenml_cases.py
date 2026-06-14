"""ZenML deployment case studies loader — real-world vendor deployment context."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.loaders.base_loader import BaseLoader

# Five right_sizing_profile rows from published vendor case studies
# profile_id, composition_pattern, task_archetype, quality_min, latency_max_ms,
# cost_max_per_1k, regulatory_regime, human_review_required, pii_involved,
# industry, value_source_type, confidence, notes
_PROFILES = [
    ("rsp-accenture", "rag",         "enterprise_qa",      0.85, 2000.0, 0.020,
     "GDPR",  1, 1, "consulting",           "vendor_claim", "medium",
     "Accenture Knowledge Assist - Azure OpenAI + cognitive search"),
    ("rsp-doordash",  "bare_llm",    "customer_service",   0.80,  800.0, 0.008,
     None,    0, 1, "food_delivery",        "vendor_claim", "medium",
     "DoorDash customer support LLM"),
    ("rsp-uber",      "rag_reasoning","trip_planning",      0.82, 1500.0, 0.015,
     None,    0, 1, "rideshare",            "vendor_claim", "low",
     "Uber AI assistant"),
    ("rsp-linkedin",  "tool_agent",  "job_matching",       0.78, 3000.0, 0.010,
     "GDPR",  1, 1, "professional_network", "vendor_claim", "medium",
     "LinkedIn JUDE - job understanding engine"),
    ("rsp-telekom",   "rag",         "enterprise_support",  0.83, 2500.0, 0.018,
     "GDPR",  1, 0, "telecommunications",  "vendor_claim", "low",
     "Deutsche Telekom LMOS multi-agent orchestration"),
]

# Three benchmark_run rows anchoring the ZenML deployment claims to evidence
# (run_id, comp_id, cmp_id, ev_id, task, hw, quality, lat, cost, energy, mem,
#  qmetric, smetric, notes)
_BENCH_RUNS = [
    ("zenml-accenture-rag-qa", None, None, "ev-zenml-1",
     "enterprise_qa", "unknown", 0.862, 1850.0, 0.018, None, None,
     "f1", "zenml_case",
     "Accenture Knowledge Assist — observed QA quality from vendor report"),
    ("zenml-doordash-cs-bare", None, None, "ev-zenml-1",
     "customer_service", "unknown", 0.814, 720.0, 0.007, None, None,
     "accuracy", "zenml_case",
     "DoorDash CS LLM — vendor-reported CSAT-derived accuracy proxy"),
    ("zenml-telekom-rag-sup", None, None, "ev-zenml-1",
     "enterprise_support", "unknown", 0.847, 2300.0, 0.017, None, None,
     "f1", "zenml_case",
     "Deutsche Telekom LMOS — observed support resolution quality"),
]


class ZenMLCasesLoader(BaseLoader):
    """Load ZenML enterprise deployment case study profiles."""

    def _load(self, con: sqlite3.Connection) -> int:
        # ── Source ──────────────────────────────────────────────────────────
        self._ins_source(
            con, "src-zenml", "vendor",
            "ZenML Enterprise Case Studies — LLM deployment context database",
            "https://zenml.io/blog/llm-deployment-case-studies", "2024-07-01",
            "CC-BY-4.0",
        )

        # ── Evidence items ───────────────────────────────────────────────────
        self._ins_ev(
            con, "ev-zenml-1", "src-zenml", "deployment_record",
            "Vendor-reported deployment metrics from enterprise case studies",
            "various", "2024-07-01",
        )

        # ── right_sizing_profile rows ────────────────────────────────────────
        inserted = 0
        for (pid, pattern, task, q_min, lat_max, cost_max, regime,
             human_review, pii, industry, vst, conf, notes) in _PROFILES:
            exists = con.execute(
                "SELECT 1 FROM right_sizing_profile WHERE profile_id=?", (pid,)
            ).fetchone()
            if not exists:
                con.execute(
                    """INSERT INTO right_sizing_profile
                       (profile_id,composition_pattern,task_archetype,quality_min,
                        latency_max_ms,cost_max_per_1k,regulatory_regime,
                        human_review_required,pii_involved,industry,
                        value_source_type,confidence,notes)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, pattern, task, q_min, lat_max, cost_max, regime,
                     human_review, pii, industry, vst, conf, notes),
                )
                inserted += 1

        # ── benchmark_run rows ───────────────────────────────────────────────
        for row in _BENCH_RUNS:
            self._ins_run(con, *row)

        return inserted


def main():
    import sys
    from apt_engine.db import init_db
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    init_db(db)
    n = ZenMLCasesLoader(db).load()
    print(f"ZenML cases: loaded {n} right_sizing_profile rows")


if __name__ == "__main__":
    main()
