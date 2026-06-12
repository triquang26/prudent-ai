"""OMB binding anchor — Experiment A2.

Compute the fraction of GenAI/LLM use cases in the US Federal AI Inventory
2025 (OMB) that carry at least one governance-binding indicator:

  * is_high_impact == "High-impact"   (rights/safety-impacting system)
  * have_ato      == "Yes"            (authority-to-operate required)
  * has_pii       == "Yes"            (personal data involved)

This self-reported fraction is the OMB binding anchor p̂_omb — an
external, non-LLM baseline for the governance-binding rate.

Run:
    PYTHONNOUSERSITE=1 uv run python scripts/run_omb_binding_anchor.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

CSV_PATH = Path("data/corpus3_omb/omb2025.csv")
OUT_DIR = Path("outputs/p3")

# GenAI/LLM relevance filter — identical to run_corpus3_omb.py
_GEN = re.compile(
    r"gener|llm|gpt|chatbot|\brag\b|summar|language model|copilot|conversational|"
    r"natural language|\bnlp\b|text generation|claude|prompt", re.I)


def _text(r: dict) -> str:
    """Concatenate the free-text fields used for GenAI relevance matching."""
    return " ".join((r.get(k) or "") for k in
                    ("use_case_name", "problem_solved", "benefits", "system_outputs"))


def is_high_impact(r: dict) -> bool:
    return (r.get("is_high_impact") or "").strip().lower() == "high-impact"


def has_ato(r: dict) -> bool:
    return (r.get("have_ato") or "").strip().lower() == "yes"


def has_pii(r: dict) -> bool:
    return (r.get("has_pii") or "").strip().lower() == "yes"


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig")))
    gen = [r for r in rows if _GEN.search(_text(r))]

    n = len(gen)

    # Per-field counts
    hi_count = sum(1 for r in gen if is_high_impact(r))
    ato_count = sum(1 for r in gen if has_ato(r))
    pii_count = sum(1 for r in gen if has_pii(r))

    # Any-field binding
    binding = [r for r in gen if is_high_impact(r) or has_ato(r) or has_pii(r)]
    n_binding = len(binding)

    def fr(x: int) -> float:
        return round(x / n, 4) if n else 0.0

    result = {
        "n_total_rows": len(rows),
        "n_genai": n,
        "n_binding": n_binding,
        "frac_binding": fr(n_binding),
        "by_field": {
            "is_high_impact": {"count": hi_count, "frac": fr(hi_count)},
            "have_ato":        {"count": ato_count, "frac": fr(ato_count)},
            "has_pii":         {"count": pii_count, "frac": fr(pii_count)},
        },
        "note": (
            "p_hat_omb = frac_binding: fraction of GenAI/LLM use cases in the US "
            "Federal AI Inventory 2025 (OMB self-reported) that carry at least one "
            "governance-binding indicator (high-impact rights/safety system, "
            "authority-to-operate required, or personal data involved). "
            "Source: US OMB AI Use Case Inventory 2025, public domain."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "omb_binding_anchor.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Markdown summary
    lines = [
        "# OMB Binding Anchor — p̂_omb (Experiment A2)",
        "",
        "**Source:** US Federal AI Use Case Inventory 2025 (OMB), public domain.",
        "",
        f"- Total AI use cases in inventory: **{len(rows)}**",
        f"- GenAI/LLM-relevant subset: **{n}**",
        f"- Cases with ≥ 1 governance-binding indicator: **{n_binding}** "
        f"({100 * fr(n_binding):.1f}%)",
        "",
        f"**p̂_omb = {fr(n_binding):.4f}  ({100 * fr(n_binding):.1f}%)**",
        "",
        "## Breakdown by binding field",
        "",
        "| Field | Condition | Count | Fraction |",
        "|---|---|---|---|",
        f"| `is_high_impact` | == \"High-impact\" | {hi_count} | {100 * fr(hi_count):.1f}% |",
        f"| `have_ato` | == \"Yes\" | {ato_count} | {100 * fr(ato_count):.1f}% |",
        f"| `has_pii` | == \"Yes\" | {pii_count} | {100 * fr(pii_count):.1f}% |",
        f"| **Any field** | (union) | **{n_binding}** | **{100 * fr(n_binding):.1f}%** |",
        "",
        "## Interpretation",
        "",
        "p̂_omb is a non-LLM, self-reported baseline governance-binding rate drawn from "
        "a legally-mandated government inventory (EO 13960 / M-24-10). It bounds the "
        "governance-binding prevalence from below for public-sector GenAI deployments "
        "and serves as an external anchor for APT's governance-axis demand estimate.",
    ]

    md_path = OUT_DIR / "omb_binding_anchor.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Print summary
    print("\n".join(lines))
    print(f"\nWrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
