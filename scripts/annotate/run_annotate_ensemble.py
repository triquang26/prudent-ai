"""Multi-LLM ensemble annotation of governance bindingness (3 model families).

A reviewer asked the binding-rate anchor to use a multi-model ensemble rather than a
single model, so that *inter-model* agreement (not just intra-prompt agreement) is the
reliability proxy. We run three instruct models from three different providers --- so
their training biases are not shared --- each with the same 3 prompt variants and rubric
as the single-model run (scripts/annotate/run_annotate_32b.py):

    Qwen2.5-32B-Instruct        (Alibaba, Apache-2.0)
    Meta-Llama-3-8B-Instruct    (Meta,    Llama-3 license)
    Mistral-7B-Instruct-v0.3    (Mistral, Apache-2.0)

BOUNDARY (the whole point): these labels measure what each case study *declares* in its
narrative --- whether the text states a governance requirement that excludes a concrete
candidate configuration. They are NOT a prediction of whether governance *truly* binds at
the optimum (that would require the unmeasured axis itself). The labels anchor the prior
probability p in the declared=>binding sweep; they are NEVER written to the substrate.

Run with the SmolVLA conda env (same as the 32B run):
  PYTHONNOUSERSITE=1 /mnt/data/sftp/data/quangpt3/miniconda3/envs/SmolVLA/bin/python \
      scripts/annotate/run_annotate_ensemble.py

Output (standardized schema that scripts/run_prob_binding.py::build_labels_by_title reads):
  outputs/p3/binding_annotation_ensemble.json
    {"per_case": [{"title", "final_label", "model_labels", "model_majority",
                   "prompt_labels"}],
     "metadata": {"models", "inter_model_fleiss_kappa", "ensemble_p_hat", "ensemble_ci_95",
                  "per_model_p_hat", "n_cases", ...}}
"""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Reuse the case loader, prompt builder, label parsing, and stats from the 32B script.
sys.path.insert(0, str(Path(__file__).parent))
from run_annotate_32b import (  # noqa: E402
    bootstrap_ci,
    build_prompts,
    extract_label,
    fleiss_kappa,
    load_cases,
    majority,
)

REPO = Path(__file__).parents[2]
OUT_JSON = REPO / "outputs/p3/binding_annotation_ensemble.json"
MAX_NEW_TOKENS = 8

# Three instruct models from three different providers (uncorrelated training bias).
# batch_size tuned to fit the 80GB H100 (32B is heavier, so a smaller batch).
MODELS: list[tuple[str, str, int]] = [
    ("qwen32b", "Qwen/Qwen2.5-32B-Instruct", 24),
    ("llama3_8b", "meta-llama/Meta-Llama-3-8B-Instruct", 64),
    ("mistral7b", "mistralai/Mistral-7B-Instruct-v0.3", 64),
]


def annotate_with_model(
    model_id: str, cases: list[dict], batch_size: int, t0: float
) -> tuple[list[str], list[list[str]]]:
    """Return (per-case majority label, per-case [3 prompt labels]) for one model.

    All 3*n prompts are generated in left-padded batches for throughput.
    """
    print(f"\n=== Loading {model_id} (bfloat16, batch={batch_size}) ===", flush=True)
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tok.padding_side = "left"  # decoder-only: pad on the left so new tokens align
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"  loaded; VRAM {torch.cuda.memory_allocated()/1e9:.1f}GB", flush=True)

    # Flatten to (case_idx, prompt_idx) -> chat-templated text.
    flat_text: list[str] = []
    for case in cases:
        for prompt in build_prompts(case["text"]):
            msgs = [{"role": "user", "content": prompt}]
            flat_text.append(
                tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            )

    flat_labels: list[str] = [""] * len(flat_text)
    n_batches = (len(flat_text) + batch_size - 1) // batch_size
    for bi in range(n_batches):
        chunk = flat_text[bi * batch_size:(bi + 1) * batch_size]
        inputs = tok(chunk, return_tensors="pt", padding=True, truncation=True,
                     max_length=2048).to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        gen = out[:, inputs["input_ids"].shape[1]:]
        for j, row in enumerate(gen):
            txt = tok.decode(row, skip_special_tokens=True).strip()
            flat_labels[bi * batch_size + j] = extract_label(txt)
        if (bi + 1) % 10 == 0 or bi == 0:
            done = (bi + 1) * batch_size
            elapsed = time.time() - t0
            rate = done / elapsed
            eta = (len(flat_text) - done) / max(rate, 1e-6)
            print(f"  [{model_id} {min(done,len(flat_text))}/{len(flat_text)} prompts] "
                  f"{rate:.1f} prompt/s | ETA {eta/60:.1f}min", flush=True)

    # Reshape flat labels back to per-case [3] and majority.
    per_case_prompt_labels = [flat_labels[i * 3:(i + 1) * 3] for i in range(len(cases))]
    per_case_majority = [majority(p) for p in per_case_prompt_labels]
    b = per_case_majority.count("BINDING")
    print(f"  {model_id} done: BINDING={b}/{len(cases)}", flush=True)

    # Free the GPU before the next family.
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return per_case_majority, per_case_prompt_labels


def main() -> None:
    t0 = time.time()
    cases = load_cases()
    n = len(cases)
    print(f"Loaded {n} governance cases. Ensemble of {len(MODELS)} models × 3 prompts.")

    # model_key -> [per-case majority]; model_key -> [per-case [3 prompt labels]]
    model_majorities: dict[str, list[str]] = {}
    model_prompt_labels: dict[str, list[list[str]]] = {}
    for key, model_id, bs in MODELS:
        maj, prompts = annotate_with_model(model_id, cases, bs, t0)
        model_majorities[key] = maj
        model_prompt_labels[key] = prompts

    keys = [k for k, _, _ in MODELS]

    # Ensemble majority = vote over the 3 model-majorities (tie -> UNDETERMINED).
    final_labels: list[str] = []
    for i in range(n):
        votes = [model_majorities[k][i] for k in keys]
        final_labels.append(majority(votes))

    # Inter-model Fleiss kappa: 3 raters = the 3 models' per-case majority labels.
    inter_model_annotations = [[model_majorities[k][i] for k in keys] for i in range(n)]
    inter_kappa = fleiss_kappa(inter_model_annotations)

    # Per-model p-hat and ensemble p-hat + bootstrap CI.
    per_model_p = {k: round(model_majorities[k].count("BINDING") / n, 4) for k in keys}
    n_binding = final_labels.count("BINDING")
    n_non = final_labels.count("NON_BINDING")
    n_und = final_labels.count("UNDETERMINED")
    p_hat = n_binding / n
    ci_lo, ci_hi = bootstrap_ci(final_labels)

    print("\n=== Ensemble results ===")
    print(f"n={n}  per-model p̂: {per_model_p}")
    print(f"ensemble: BINDING={n_binding} NON_BINDING={n_non} UNDETERMINED={n_und}")
    print(f"ensemble p̂ = {p_hat:.4f}  95% CI [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"inter-model Fleiss κ = {inter_kappa:.3f}")
    print(f"total time {(time.time()-t0)/60:.1f} min")

    per_case = []
    for i in range(n):
        per_case.append({
            "title": cases[i]["title"],
            "final_label": final_labels[i],
            "model_majority": {k: model_majorities[k][i] for k in keys},
            "model_labels": {k: model_prompt_labels[k][i] for k in keys},
        })

    result = {
        "per_case": per_case,
        "metadata": {
            "method": "multi-llm-ensemble",
            "models": {k: mid for k, mid, _ in MODELS},
            "n_models": len(MODELS),
            "n_prompts_per_model": 3,
            "n_cases": n,
            "inter_model_fleiss_kappa": round(inter_kappa, 3),
            "ensemble_p_hat": round(p_hat, 4),
            "ensemble_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
            "per_model_p_hat": per_model_p,
            "ensemble_counts": {"BINDING": n_binding, "NON_BINDING": n_non,
                                "UNDETERMINED": n_und},
            "note": "Labels measure what each case study DECLARES (a governance "
                    "requirement excluding a concrete candidate), not whether governance "
                    "truly binds. They anchor the prior p; never written to the substrate. "
                    "Inter-model agreement is a reliability proxy, not ground truth.",
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
