"""Score human–LLM agreement on the binding-rate anchor (Phase 2).

After a human fills the `human_label` column of human_annotation_sheet.csv, we measure how
well the LLM ensemble agrees with the human on the labeled subset:
  - Cohen's kappa between the human and the ensemble majority (human vs machine — a valid
    Cohen's kappa over the two raters);
  - per-model Cohen's kappa (human vs each model's majority);
  - raw agreement and the confusion of labels.

HONEST CAVEAT (reported in output and the paper): only ONE human annotator is available,
so *inter-human* reliability (the classic two-annotator Cohen's kappa) is UNDEFINED. We
report human–LLM agreement as the validation and do not claim two-annotator reliability.

Run:
  PYTHONNOUSERSITE=1 uv run python scripts/annotate/score_human_agreement.py

Inputs:
  outputs/p3/human_annotation_sheet.csv          (human_label filled in)
  outputs/p3/binding_annotation_ensemble.json    (model + ensemble labels)
Output:
  outputs/p3/human_llm_agreement.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
SHEET = REPO / "outputs/p3/human_annotation_sheet.csv"
ENSEMBLE = REPO / "outputs/p3/binding_annotation_ensemble.json"
OUT = REPO / "outputs/p3/human_llm_agreement.json"

LABELS = ["BINDING", "NON_BINDING", "UNDETERMINED"]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa between two raters over the categorical LABELS."""
    n = len(a)
    if n == 0:
        return float("nan")
    idx = {lab: i for i, lab in enumerate(LABELS)}
    k = len(LABELS)
    conf = [[0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        conf[idx[x]][idx[y]] += 1
    po = sum(conf[i][i] for i in range(k)) / n
    row = [sum(conf[i]) / n for i in range(k)]
    col = [sum(conf[i][j] for i in range(k)) / n for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k))
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def main() -> None:
    if not SHEET.exists():
        sys.exit(f"missing {SHEET}")
    ens = {c["title"]: c for c in json.loads(ENSEMBLE.read_text())["per_case"]}

    human, ensemble, per_model = [], [], {"qwen32b": [], "llama3_8b": [], "mistral7b": []}
    n_filled = 0
    for r in csv.DictReader(SHEET.open()):
        lab = (r.get("human_label") or "").strip().upper()
        if lab not in LABELS:
            continue  # unlabeled row — skip
        title = r["title"]
        case = ens.get(title)
        if case is None:
            continue
        n_filled += 1
        human.append(lab)
        ensemble.append(case["final_label"])
        for mk in per_model:
            per_model[mk].append(case["model_majority"][mk])

    if n_filled == 0:
        sys.exit("no human labels found — fill the human_label column first")

    agree = sum(1 for h, e in zip(human, ensemble, strict=True) if h == e) / n_filled
    result = {
        "n_labeled": n_filled,
        "human_vs_ensemble": {
            "cohen_kappa": round(cohen_kappa(human, ensemble), 3),
            "raw_agreement": round(agree, 3),
        },
        "human_vs_each_model": {
            mk: round(cohen_kappa(human, per_model[mk]), 3) for mk in per_model
        },
        "human_label_counts": {lab: human.count(lab) for lab in LABELS},
        "ensemble_label_counts": {lab: ensemble.count(lab) for lab in LABELS},
        "caveat": "Single human annotator: inter-human Cohen's kappa is UNDEFINED. We "
                  "report human-LLM agreement as the validation; two-annotator reliability "
                  "is not established.",
    }
    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
