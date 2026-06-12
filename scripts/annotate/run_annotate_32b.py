"""LLM-ensemble annotation using Qwen2.5-32B-Instruct (bfloat16, H100 80GB).

Run with SmolVLA conda env:
  PYTHONNOUSERSITE=1 /mnt/data/sftp/data/quangpt3/miniconda3/envs/SmolVLA/bin/python \
      scripts/annotate/run_annotate_32b.py

Model: Qwen2.5-32B-Instruct (Apache-2.0, ~64GB bfloat16)
Labels: BINDING / NON_BINDING / UNDETERMINED
Ensemble: 3 prompt variants, majority vote
Output: outputs/p3/binding_annotation.json (overwrites heuristic run)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

REPO = Path(__file__).parents[2]
SNAPSHOT = REPO / "data/zenml_llmops_snapshot.json"
OUT_JSON = REPO / "outputs/p3/binding_annotation.json"
OUT_PER_CASE = REPO / "outputs/p3/binding_annotation_per_case.json"
MODEL_ID = "Qwen/Qwen2.5-32B-Instruct"
MAX_NEW_TOKENS = 10
SEED = 42

LABEL_RE = re.compile(r"\b(BINDING|NON_BINDING|UNDETERMINED)\b")

# Governance filter — mirrors query_prior.py REGULATED_INDUSTRIES + TAG_TO_AXIS
_REGULATED = {
    "Healthcare", "Finance", "Legal", "Insurance", "Government",
    "Education", "Energy", "Transportation", "Cybersecurity",
    "Defense", "Pharmaceutical", "Banking",
}
_GOV_TAGS = {"regulatory_compliance", "high_stakes_application",
             "content_moderation", "fraud_detection"}


def load_cases() -> list[dict]:
    rows = json.loads(SNAPSHOT.read_text())
    out = []
    for r in rows:
        tags = set((r.get("application_tags") or "").split(","))
        if r.get("industry") in _REGULATED or tags & _GOV_TAGS:
            title = (r.get("title") or "")[:80]
            # Use first 2000 chars of full_summary as the governance text
            text = (r.get("short_summary") or "").strip()
            full = (r.get("full_summary") or "").strip()
            if full:
                text = text + "\n\n" + full[:2000]
            out.append({"title": title, "text": text.strip()})
    return out


# Few-shot examples (2 BINDING + 2 NON_BINDING) derived from keyword-explicit cases
FEW_SHOT_BINDING = [
    "Data must remain on-premises; no external API calls permitted. Only self-hosted open-weights models are admissible.",
    "System requires FedRAMP High authorization. Proprietary cloud models cannot be used; deployment must use an authority-to-operate approved configuration.",
]
FEW_SHOT_NON_BINDING = [
    "Agency must maintain an audit log of all AI decisions for 7 years and provide explainability reports on request.",
    "The system must disclose when a user is interacting with an AI. All outputs must include a transparency notice.",
]


def build_prompts(text: str) -> list[str]:
    """3 prompt variants for the ensemble."""
    p1 = (
        "You are an AI governance expert. Classify the following governance requirement.\n\n"
        "BINDING: The requirement restricts which AI model configurations are admissible "
        "(e.g., mandates self-hosting, prohibits certain vendors, requires specific certifications "
        "that exclude some models).\n"
        "NON_BINDING: The requirement is procedural or disclosure-only (audit logs, transparency "
        "notices, explainability) — it does not restrict model selection.\n"
        "UNDETERMINED: Insufficient information to classify.\n\n"
        f"Requirement: {text[:1500]}\n\n"
        "Respond with exactly one word: BINDING, NON_BINDING, or UNDETERMINED."
    )
    p2 = (
        "Does this AI governance requirement EXCLUDE specific model configurations from use "
        "(e.g., bans cloud APIs, mandates open-weights, requires FedRAMP/ATO)? "
        "Answer BINDING if yes, NON_BINDING if it is procedural/disclosure only, "
        "UNDETERMINED if unclear.\n\n"
        f"Requirement: {text[:1500]}\n\nAnswer:"
    )
    p3 = (
        "Examples of BINDING requirements (restrict model choice):\n"
        f"- {FEW_SHOT_BINDING[0]}\n"
        f"- {FEW_SHOT_BINDING[1]}\n\n"
        "Examples of NON_BINDING requirements (procedural/disclosure only):\n"
        f"- {FEW_SHOT_NON_BINDING[0]}\n"
        f"- {FEW_SHOT_NON_BINDING[1]}\n\n"
        f"Classify this requirement as BINDING, NON_BINDING, or UNDETERMINED:\n{text[:1500]}\n\nAnswer:"
    )
    return [p1, p2, p3]


def extract_label(text: str) -> str:
    m = LABEL_RE.search(text.upper())
    return m.group(1) if m else "UNDETERMINED"


def majority(labels: list[str]) -> str:
    counts = {"BINDING": 0, "NON_BINDING": 0, "UNDETERMINED": 0}
    for l in labels:
        counts[l] = counts.get(l, 0) + 1
    return max(counts, key=counts.get)


def bootstrap_ci(labels: list[str], n_boot: int = 2000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    arr = np.array([1 if l == "BINDING" else 0 for l in labels])
    boot = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def fleiss_kappa(annotations: list[list[str]]) -> float:
    """Compute Fleiss kappa over n_cases × n_raters binary (BINDING vs not) matrix."""
    n = len(annotations)
    k = len(annotations[0])  # raters
    cats = ["BINDING", "NON_BINDING", "UNDETERMINED"]
    # n x 3 matrix
    mat = np.zeros((n, len(cats)))
    for i, rater_labels in enumerate(annotations):
        for l in rater_labels:
            j = cats.index(l) if l in cats else 2
            mat[i, j] += 1
    P_i = ((mat ** 2).sum(axis=1) - k) / (k * (k - 1))
    P_bar = P_i.mean()
    p_j = mat.sum(axis=0) / mat.sum()
    P_e = (p_j ** 2).sum()
    if P_e == 1.0:
        return 1.0
    return float((P_bar - P_e) / (1 - P_e))


def main():
    t0 = time.time()
    print(f"Loading model {MODEL_ID} in bfloat16 on GPU...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"Model loaded in {time.time()-t0:.1f}s. VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB")

    cases = load_cases()
    print(f"Annotating {len(cases)} governance cases × 3 prompts...")

    per_case_labels: list[list[str]] = []  # [case_idx][prompt_idx] -> label
    per_case_majority: list[str] = []

    for i, case in enumerate(cases):
        prompts = build_prompts(case["text"])
        labels_for_case = []
        for prompt in prompts:
            msgs = [{"role": "user", "content": prompt}]
            text_input = tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True
            )
            inputs = tokenizer(text_input, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            new_tokens = out[0][inputs["input_ids"].shape[1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            label = extract_label(raw)
            labels_for_case.append(label)

        maj = majority(labels_for_case)
        per_case_labels.append(labels_for_case)
        per_case_majority.append(maj)

        if (i + 1) % 50 == 0 or i == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(cases) - i - 1) / rate
            b_count = per_case_majority.count("BINDING")
            print(f"  [{i+1}/{len(cases)}] BINDING so far: {b_count} | {rate:.1f} cases/s | ETA {eta/60:.1f}min")
            sys.stdout.flush()

    # Compute stats
    n = len(per_case_majority)
    n_binding = per_case_majority.count("BINDING")
    n_non = per_case_majority.count("NON_BINDING")
    n_und = per_case_majority.count("UNDETERMINED")
    p_hat = n_binding / n
    ci_lo, ci_hi = bootstrap_ci(per_case_majority)
    kappa = fleiss_kappa(per_case_labels)

    print(f"\n=== Results ===")
    print(f"n={n}, BINDING={n_binding} ({100*p_hat:.1f}%), NON_BINDING={n_non}, UNDETERMINED={n_und}")
    print(f"p̂_binding = {p_hat:.4f}  95% CI [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"Fleiss κ = {kappa:.3f}")
    print(f"Total time: {(time.time()-t0)/60:.1f} min")

    result = {
        "metadata": {
            "method": "llm-ensemble",
            "model": MODEL_ID,
            "model_params": "32B bfloat16",
            "n_prompts": 3,
            "n_cases": n,
            "note": "Qwen2.5-32B-Instruct (Apache-2.0) × 3 prompt variants, majority vote. "
                    "Labels are LLM-derived measurements, not human gold truth.",
        },
        "n_binding": n_binding,
        "n_non_binding": n_non,
        "n_undetermined": n_und,
        "p_hat_binding": round(p_hat, 4),
        "ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "fleiss_kappa": round(kappa, 3),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    per_case_out = [
        {"title": cases[i]["title"], "majority_label": per_case_majority[i], "prompt_labels": per_case_labels[i]}
        for i in range(n)
    ]
    OUT_PER_CASE.write_text(json.dumps(per_case_out, indent=2))
    print(f"\nWrote {OUT_JSON} and {OUT_PER_CASE}")


if __name__ == "__main__":
    main()
