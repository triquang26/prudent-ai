"""Build a human-annotation sheet for the binding-rate anchor.

A reviewer asked for a human anchor on the LLM ensemble: a person reads the case-study
narrative and labels whether it DECLARES a governance requirement that excludes a concrete
candidate configuration (same question the LLMs answer). We prioritize the cases where the
three ensemble models DISAGREE --- those are the hard, informative cases where a human
anchor matters most --- plus a random sample so the labeled subset is not only hard cases.

The human judges the SAME thing the LLMs do: what the text *declares*, not whether
governance *truly* binds. Labels here anchor the prior p; they are never written to the
substrate.

Run (any env with the repo on path):
  PYTHONNOUSERSITE=1 uv run python scripts/annotate/make_human_kit.py

Inputs:
  data/zenml_llmops_snapshot.json
  outputs/p3/binding_annotation_ensemble.json   (for model-disagreement prioritization)
Outputs:
  outputs/p3/human_annotation_sheet.csv   (fill the human_label column)
  outputs/p3/human_annotation_sheet.md    (readable version with full text + rubric)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
SNAPSHOT = REPO / "data/zenml_llmops_snapshot.json"
ENSEMBLE = REPO / "outputs/p3/binding_annotation_ensemble.json"
OUT_CSV = REPO / "outputs/p3/human_annotation_sheet.csv"
OUT_MD = REPO / "outputs/p3/human_annotation_sheet.md"

N_TARGET = 150
SEED = 42
SUMMARY_CHARS = 2500  # readable excerpt length in the .md sheet

RUBRIC = (
    "RUBRIC — read each narrative and choose ONE label for what the text DECLARES "
    "(not what you guess truly binds):\n"
    "  BINDING       = the text states a governance/compliance requirement that EXCLUDES "
    "a concrete candidate configuration (e.g. 'data may not leave on-prem' => no API "
    "models; 'FedRAMP/ATO required' => excludes uncertified configs).\n"
    "  NON_BINDING   = governance is procedural/disclosure only (audit log, transparency "
    "notice, explainability) — the cheapest config is still admissible.\n"
    "  UNDETERMINED  = the text is insufficient to tell (industry/compliance tag present "
    "but no candidate-excluding mandate stated).\n"
)


def _normalize_title(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:40]


def main() -> None:
    rows = json.loads(SNAPSHOT.read_text())
    # Index governance cases by the same 80-char title key the ensemble used.
    by_title = {(r.get("title") or "")[:80]: r for r in rows}

    if not ENSEMBLE.exists():
        sys.exit(f"ensemble file missing: {ENSEMBLE} — run run_annotate_ensemble.py first")
    ens = json.loads(ENSEMBLE.read_text())
    per_case = ens["per_case"]

    # Disagreement score: number of distinct model-majority labels (3 = max disagreement).
    def disagreement(case: dict) -> int:
        return len(set(case["model_majority"].values()))

    ranked = sorted(per_case, key=lambda c: (-disagreement(c), c["title"]))
    disagreeing = [c for c in ranked if disagreement(c) >= 2]

    import random
    rng = random.Random(SEED)
    # Take all disagreeing (capped), then fill to N_TARGET with a random sample of the rest.
    chosen = list(disagreeing[:N_TARGET])
    chosen_titles = {c["title"] for c in chosen}
    remainder = [c for c in per_case if c["title"] not in chosen_titles]
    rng.shuffle(remainder)
    for c in remainder:
        if len(chosen) >= N_TARGET:
            break
        chosen.append(c)

    # Stable order for the sheet: disagreement first, then title.
    chosen.sort(key=lambda c: (-disagreement(c), c["title"]))

    # CSV (machine-mergeable). human_label left blank for the annotator.
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "title", "industry", "model_qwen32b", "model_llama3_8b",
                    "model_mistral7b", "n_distinct_model_labels", "human_label",
                    "full_summary_excerpt"])
        for i, c in enumerate(chosen):
            row = by_title.get(c["title"][:80], {})
            mm = c["model_majority"]
            w.writerow([
                i, c["title"], row.get("industry", ""),
                mm.get("qwen32b", ""), mm.get("llama3_8b", ""), mm.get("mistral7b", ""),
                disagreement(c), "",
                (row.get("full_summary") or row.get("short_summary") or "")[:SUMMARY_CHARS]
                .replace("\n", " "),
            ])

    # Markdown (human-readable: full rubric + per-case text + a blank label line).
    n_disagree = sum(1 for c in chosen if disagreement(c) >= 2)
    lines = [
        "# Human annotation sheet — governance bindingness (DECLARED)",
        "",
        f"{len(chosen)} cases: {n_disagree} where the 3 models disagree (prioritized) + "
        f"{len(chosen)-n_disagree} random.",
        "",
        "Fill the `human_label` in `human_annotation_sheet.csv` (BINDING / NON_BINDING / "
        "UNDETERMINED). The text excerpts below are for reading.",
        "",
        "```",
        RUBRIC.rstrip(),
        "```",
        "",
        "---",
        "",
    ]
    for i, c in enumerate(chosen):
        row = by_title.get(c["title"][:80], {})
        mm = c["model_majority"]
        lines += [
            f"## [{i}] {c['title']}",
            f"- industry: **{row.get('industry','')}** | model votes: "
            f"qwen={mm.get('qwen32b','')}, llama3={mm.get('llama3_8b','')}, "
            f"mistral={mm.get('mistral7b','')} | disagreement={disagreement(c)}",
            "",
            (row.get("full_summary") or row.get("short_summary") or "")[:SUMMARY_CHARS],
            "",
            "`human_label =` __________",
            "",
            "---",
            "",
        ]
    OUT_MD.write_text("\n".join(lines))
    print(f"Wrote {OUT_CSV} and {OUT_MD}")
    print(f"  {len(chosen)} cases ({n_disagree} disagreeing + {len(chosen)-n_disagree} random)")


if __name__ == "__main__":
    main()
