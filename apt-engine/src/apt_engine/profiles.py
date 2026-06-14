"""Right-sizing profiles for composition patterns."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .db import connect, DB_PATH

@dataclass
class Profile:
    profile_id: str
    composition_pattern: str
    task_archetype: Optional[str]
    quality_min: Optional[float]
    latency_max_ms: Optional[float]
    cost_max_per_1k: Optional[float]
    regulatory_regime: Optional[str]
    human_review_required: bool
    pii_involved: bool
    industry: Optional[str]
    confidence: str
    notes: Optional[str]

DEFAULT_PROFILES = [
    Profile("prof-bare-llm","bare_llm","general_qa",0.75,500.0,0.02,None,False,False,None,"high","Default bare LLM for general QA"),
    Profile("prof-rag","rag","document_qa",0.82,1000.0,0.015,None,False,False,None,"high","RAG pipeline for document-grounded QA"),
    Profile("prof-rag-reasoning","rag_reasoning","complex_qa",0.85,2000.0,0.025,"HIPAA",True,True,"healthcare","medium","Clinical reasoning RAG with HIPAA compliance"),
    Profile("prof-tool-agent","tool_agent","code_generation",0.80,3000.0,0.03,None,False,False,"engineering","high","Tool-augmented agent for code tasks"),
    Profile("prof-web-nav","web_nav","web_automation",0.60,10000.0,0.05,None,False,False,None,"medium","Web navigation agent"),
    Profile("prof-multi-agent","multi_agent","enterprise_workflow",0.85,5000.0,0.04,"GDPR",True,True,"enterprise","low","Multi-agent enterprise workflow with GDPR"),
]

def load_profiles(db_path=None) -> list[Profile]:
    con = connect(db_path or DB_PATH)
    rows = con.execute("SELECT * FROM right_sizing_profile").fetchall()
    con.close()
    return [Profile(
        r["profile_id"], r["composition_pattern"], r["task_archetype"],
        r["quality_min"], r["latency_max_ms"], r["cost_max_per_1k"],
        r["regulatory_regime"], bool(r["human_review_required"]),
        bool(r["pii_involved"]), r["industry"], r["confidence"] or "medium",
        r["notes"]
    ) for r in rows]

def seed_default_profiles(db_path=None):
    con = connect(db_path or DB_PATH)
    for p in DEFAULT_PROFILES:
        con.execute("INSERT OR IGNORE INTO right_sizing_profile VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p.profile_id, p.composition_pattern, p.task_archetype,
             p.quality_min, p.latency_max_ms, p.cost_max_per_1k,
             p.regulatory_regime, int(p.human_review_required),
             int(p.pii_involved), p.industry, "benchmark", p.confidence, p.notes))
    con.commit(); con.close()
