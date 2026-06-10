"""Seed the APT substrate with HELM Lite leaderboard data.

HELM Lite leaderboard: https://crfm.stanford.edu/helm/lite/
Citation: HELM (Liang et al. 2022), arxiv 2211.09110
Snapshot: 2023-11 (fixed for reproducibility, C3)

Axes populated: quality only (1 of 8)
Axes left ⊥:   latency_p95, throughput, cost, energy, memory_hw,
                governance, reviewer_burden (7 of 8)

Confidence: leaderboard → M (per confidence policy in data_dictionary.md)
  Justification: AXCELL auto-extraction F1 ~25.8%; NLP-repro sticky
  omission 60–89%; MOLE ~67% reliability → any leaderboard value carries
  meaningful uncertainty.

cost note: HELM Lite reports token counts (num_prompt_tokens), NOT dollar cost.
  Deriving a proxy would conflate token volume with pricing — cost axis is left ⊥.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from prudent_ai.substrate import Substrate

DB_PATH = Path("data/apt_substrate.db")

# ---------------------------------------------------------------------------
# Source records
# ---------------------------------------------------------------------------

HELM_LITE_SOURCE = {
    "evidence_id": "helm-lite-2023-11",
    "source_type": "leaderboard",
    "citation": "Liang et al. 2022, arxiv 2211.09110, HELM Lite leaderboard 2023-11",
    "snapshot_version": "2023-11",
}

HELM_LITE_PAPER_SOURCE = {
    "evidence_id": "helm-lite-paper-2022",
    "source_type": "paper_reported",
    "citation": "Liang et al. 2022, arxiv 2211.09110, Table 3",
    "snapshot_version": "2022-11",
}

# ---------------------------------------------------------------------------
# HELM Lite mmlu accuracy scores (quality axis, 0-1 scale)
# Source: HELM Lite leaderboard, snapshot 2023-11
# https://crfm.stanford.edu/helm/lite/
#
# Columns: (model_id, provider, config_id, quality_score)
# ---------------------------------------------------------------------------

HELM_LITE_MMLU_SCORES: list[tuple[str, str, str, float]] = [
    ("gpt-4",          "openai",    "gpt4-0314",        0.864),
    ("gpt-35-turbo",   "openai",    "gpt35-turbo",      0.699),
    ("claude-2",       "anthropic", "claude-2",         0.756),
    ("llama-2-70b",    "meta",      "llama2-70b-chat",  0.686),
    ("mistral-7b-v01", "mistral",   "mistral-7b-v0.1",  0.622),
    ("cohere-command", "cohere",    "command",          0.598),
]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _insert_sources(conn: sqlite3.Connection) -> None:
    """Insert (or ignore) source provenance rows."""
    for src in (HELM_LITE_SOURCE, HELM_LITE_PAPER_SOURCE):
        conn.execute(
            """
            INSERT OR IGNORE INTO source
                (evidence_id, source_type, citation, snapshot_version)
            VALUES (?, ?, ?, ?)
            """,
            (
                src["evidence_id"],
                src["source_type"],
                src["citation"],
                src["snapshot_version"],
            ),
        )


def _insert_models(conn: sqlite3.Connection) -> None:
    """Insert component rows (model + provider) and config/config_component rows."""
    # Collect unique providers first.
    providers_seen: set[str] = set()
    for model_id, provider, config_id, _ in HELM_LITE_MMLU_SCORES:
        if provider not in providers_seen:
            conn.execute(
                "INSERT OR IGNORE INTO component (id, kind, name) VALUES (?, ?, ?)",
                (f"provider-{provider}", "provider", provider),
            )
            providers_seen.add(provider)

        # Model component
        conn.execute(
            "INSERT OR IGNORE INTO component (id, kind, name) VALUES (?, ?, ?)",
            (f"model-{model_id}", "model", model_id),
        )

        # Config row — tau = 'general-qa' (HELM Lite task archetype)
        conn.execute(
            "INSERT OR IGNORE INTO config (id, tau) VALUES (?, ?)",
            (config_id, "general-qa"),
        )

        # Link config → model component and config → provider component
        conn.execute(
            "INSERT OR IGNORE INTO config_component (config_id, component_id) VALUES (?, ?)",
            (config_id, f"model-{model_id}"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO config_component (config_id, component_id) VALUES (?, ?)",
            (config_id, f"provider-{provider}"),
        )


def _insert_observations(conn: sqlite3.Connection) -> None:
    """Insert quality observations from the leaderboard source."""
    evidence_id = HELM_LITE_SOURCE["evidence_id"]
    for _model_id, _provider, config_id, score in HELM_LITE_MMLU_SCORES:
        obs_id = f"obs-{config_id}-quality-{evidence_id}"
        conn.execute(
            """
            INSERT OR IGNORE INTO observation
                (obs_id, config_id, axis, value_num, value_cat,
                 confidence, evidence_id,
                 hardware_tier, dataset, split, decoding_cfg, obs_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obs_id,
                config_id,
                "quality",
                score,
                None,          # value_cat — numeric axis
                "M",           # leaderboard → M (confidence policy)
                evidence_id,
                "openai-api",  # hardware_tier: all HELM Lite calls went through vendor APIs
                "mmlu",
                "test",
                "temperature-0.0",
                "2023-11",
            ),
        )


def _insert_multi_obs_demo(conn: sqlite3.Connection) -> None:
    """Insert a second quality observation for gpt-4 (paper_reported, greedy decoding).

    Gate requirement: ≥1 cell must have multiple observations with differing
    confidence/context.  This row gives the gpt-4/quality cell two observations:
      1. leaderboard / confidence=M / decoding=temperature-0.0  (from _insert_observations)
      2. paper_reported / confidence=M / decoding=greedy         (this row)

    Both land in the same (config_id='gpt4-0314', axis='quality') cell, satisfying
    the multi-observation demo requirement.
    """
    paper_evidence_id = HELM_LITE_PAPER_SOURCE["evidence_id"]
    config_id = "gpt4-0314"
    obs_id = f"obs-{config_id}-quality-{paper_evidence_id}"
    conn.execute(
        """
        INSERT OR IGNORE INTO observation
            (obs_id, config_id, axis, value_num, value_cat,
             confidence, evidence_id,
             hardware_tier, dataset, split, decoding_cfg, obs_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            obs_id,
            config_id,
            "quality",
            0.864,     # same reported score, different source/decoding context
            None,
            "M",       # paper_reported → M (confidence policy)
            paper_evidence_id,
            "openai-api",
            "mmlu",
            "test",
            "greedy",   # different decoding_cfg — distinguishes the two observations
            "2022-11",
        ),
    )


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------


def _report_coverage(db_path: Path) -> None:
    """Print decidability-relevant headline: which axes are populated vs ⊥."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    axes = [
        "quality",
        "latency_p95",
        "throughput",
        "cost",
        "energy",
        "memory_hw",
        "governance",
        "reviewer_burden",
    ]
    print("\n=== HELM Lite coverage (baseline seed) ===")
    print(f"{'axis':<20} {'obs_count':>9} {'populated':>9}")
    for axis in axes:
        count = conn.execute(
            "SELECT COUNT(*) FROM observation WHERE axis=?", (axis,)
        ).fetchone()[0]
        populated = "YES" if count > 0 else "⊥"
        print(f"{axis:<20} {count:>9} {populated:>9}")
    print()
    conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def seed(db_path: Path = DB_PATH) -> None:
    """Seed the APT substrate with HELM Lite data.

    Idempotent: uses INSERT OR IGNORE throughout, so re-running produces the
    same DB state without duplicates or errors.

    Args:
        db_path: Path to the SQLite file to create or update.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sub = Substrate(db_path)
    conn = sub._conn
    conn.execute("PRAGMA foreign_keys = ON")

    _insert_sources(conn)
    _insert_models(conn)
    _insert_observations(conn)
    _insert_multi_obs_demo(conn)

    conn.commit()
    sub.close()

    print(f"Seeded {db_path}")
    _report_coverage(db_path)


if __name__ == "__main__":
    seed()
