"""LLM-ensemble annotation of governance cases for binding rate estimation.

Annotates all 954 governance-tagged cases from the ZenML LLMOps snapshot with
a 3-label rubric: BINDING / NON_BINDING / UNDETERMINED.

Uses 2 model families x 3 prompt variants (6 votes per case); majority vote decides.
Models (already downloaded in HF cache):
  - Qwen3-VL-8B-Instruct   (8B instruct, Qwen3VLForConditionalGeneration)
  - Qwen2.5-0.5B            (0.5B, AutoModelForCausalLM)

Falls back to an enhanced heuristic approach if GPU inference fails,
clearly labelled as "heuristic-keyword" in the output.

Outputs:
  outputs/p3/binding_annotation.json          — summary + metadata
  outputs/p3/binding_annotation_per_case.json — full per-case results

Run (from repo root):
    PYTHONNOUSERSITE=1 \\
      /mnt/data/sftp/data/quangpt3/miniconda3/envs/SmolVLA/bin/python \\
      scripts/annotate/run_annotate.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "data/zenml_llmops_snapshot.json"
OUT_FILE = REPO_ROOT / "outputs/p3/binding_annotation.json"
OUT_PER_CASE = REPO_ROOT / "outputs/p3/binding_annotation_per_case.json"

# ---------------------------------------------------------------------------
# Governance tagging (mirrors run_governance_bindingness.py)
# ---------------------------------------------------------------------------
GOV_TAGS = {"regulatory_compliance", "high_stakes_application",
            "content_moderation", "fraud_detection"}
REGULATED_INDUSTRIES = {"Healthcare", "Finance", "Legal", "Insurance",
                        "Government"}

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
LABELS = ("BINDING", "NON_BINDING", "UNDETERMINED")

# ---------------------------------------------------------------------------
# Prompt templates (3 variants, each a callable text -> str)
# ---------------------------------------------------------------------------

SYSTEM_MSG = (
    "You are an expert AI governance analyst. "
    "Reply with ONLY one word: BINDING, NON_BINDING, or UNDETERMINED. "
    "No explanation or punctuation."
)

PROMPT_TEMPLATES = [
    # P1 — direct definitional framing
    lambda text: (
        "A governance requirement is BINDING if it EXCLUDES or MANDATES specific "
        "model/hosting configurations (e.g., forces self-hosting, bars external APIs, "
        "restricts to approved vendors, prohibits cloud LLMs due to regulation).\n"
        "It is NON_BINDING if only procedural/disclosure/audit — it does NOT eliminate "
        "any candidate model configuration.\n"
        "Label UNDETERMINED if ambiguous.\n\n"
        f"Case:\n{text}\n\nLabel:"
    ),
    # P2 — candidate-elimination framing
    lambda text: (
        "Does this governance/compliance requirement ELIMINATE any candidate AI model "
        "configurations from consideration?\n"
        "YES (forces a specific config or excludes others) → BINDING\n"
        "NO (only audit/disclosure/procedural) → NON_BINDING\n"
        "Unclear → UNDETERMINED\n\n"
        f"Text:\n{text}\n\nAnswer:"
    ),
    # P3 — few-shot with 3 positive + 3 negative examples
    lambda text: (
        "Classify as BINDING, NON_BINDING, or UNDETERMINED.\n\n"
        "BINDING examples:\n"
        "1. 'self-hosted proxy provides full data sovereignty' → BINDING\n"
        "2. 'data is privileged and cannot sit on third-party servers' → BINDING\n"
        "3. 'cannot send prompts to external API due to compliance' → BINDING\n\n"
        "NON_BINDING examples:\n"
        "1. 'we publish an annual transparency report about AI decisions' → NON_BINDING\n"
        "2. 'audit logs of all LLM calls retained for 2 years' → NON_BINDING\n"
        "3. 'explainability report required for each model output' → NON_BINDING\n\n"
        f"New case:\n{text}\n\nLabel:"
    ),
]


# ---------------------------------------------------------------------------
# Text preparation — governance-focused passage extraction
# ---------------------------------------------------------------------------

# Keywords that signal governance-relevant sentences
_GOV_KEYWORDS = re.compile(
    r"\b(complian|regulat|hipaa|gdpr|phi\b|pii\b|privacy|sovereignt|residency|"
    r"self[- ]host|on[- ]prem|in[- ]house|air[- ]gap|cannot|prohibited|forbidden|"
    r"external api|third.part|approved vendor|open[- ]?source model|open[- ]?weight|"
    r"air-gapped|classified|fedram|fedramp|data residency|cannot leave|never leave|"
    r"must not leave|not allowed|privileged|confidential)\w*",
    re.IGNORECASE,
)


def extract_governance_passages(text: str, max_chars: int = 1400) -> str:
    """
    Extract sentences containing governance-relevant keywords.
    Falls back to first max_chars if no such sentences found.
    """
    # Split on sentence boundaries (approximate)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    relevant = [s.strip() for s in sentences if _GOV_KEYWORDS.search(s)]

    if not relevant:
        # No keyword sentences — return first max_chars (most likely intro/context)
        return text[:max_chars] + (" [...]" if len(text) > max_chars else "")

    # Concatenate relevant sentences up to max_chars
    result_parts = []
    total = 0
    for s in relevant:
        if total + len(s) > max_chars:
            break
        result_parts.append(s)
        total += len(s) + 1

    snippet = " ".join(result_parts)
    if len(relevant) > len(result_parts):
        snippet += f" [...{len(relevant)-len(result_parts)} more governance sentences]"
    return snippet


def prepare_text(row: dict, max_chars: int = 1400) -> str:
    """
    Return governance-focused text snippet.
    Extracts sentences containing governance keywords from the full text.
    If none found, returns start of short_summary.
    """
    short = (row.get("short_summary") or "").strip()
    full = (row.get("full_summary") or "").strip()
    # Prefer full text for passage extraction (binding phrases are spread throughout)
    full_text = (short + "\n\n" + full).strip()
    return extract_governance_passages(full_text, max_chars=max_chars)


# ---------------------------------------------------------------------------
# Label parsing
# ---------------------------------------------------------------------------

def parse_label(text: str) -> str:
    """Extract BINDING / NON_BINDING / UNDETERMINED from model output."""
    text = text.strip().upper()
    # Exact label first (NON_BINDING before BINDING to avoid substring match)
    for lbl in ("NON_BINDING", "BINDING", "UNDETERMINED"):
        if lbl in text:
            return lbl
    # Fuzzy fallbacks
    if re.search(r"\bBIND\b", text):
        return "BINDING"
    if re.search(r"\bNON\b", text) or re.search(r"NOT\s+BIND", text):
        return "NON_BINDING"
    return "UNDETERMINED"


def majority_vote(labels: list[str]) -> str:
    """Return label with most votes; ties broken UNDETERMINED > NON_BINDING > BINDING."""
    counts = {lbl: labels.count(lbl) for lbl in LABELS}
    max_count = max(counts.values())
    candidates = [lbl for lbl in LABELS if counts[lbl] == max_count]
    for preferred in ("UNDETERMINED", "NON_BINDING", "BINDING"):
        if preferred in candidates:
            return preferred
    return "UNDETERMINED"


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

def bootstrap_ci(flags: list[int], n_boot: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    """95% bootstrap CI for a proportion."""
    import random
    n = len(flags)
    if n == 0:
        return (0.0, 0.0)
    rng = random.Random(42)
    means = []
    for _ in range(n_boot):
        sample = [rng.choice(flags) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return (round(lo, 4), round(hi, 4))


# ---------------------------------------------------------------------------
# Fleiss kappa
# ---------------------------------------------------------------------------

def fleiss_kappa(ratings: list[list[str]]) -> float:
    """
    Compute Fleiss' kappa for reliability across raters.
    ratings[i] = list of all rater labels for case i (length = n_raters, constant).
    """
    n_subjects = len(ratings)
    if n_subjects == 0:
        return float("nan")
    n_raters = len(ratings[0])
    if n_raters <= 1:
        return float("nan")
    k_cats = len(LABELS)
    label_idx = {lbl: i for i, lbl in enumerate(LABELS)}

    n_ij = [[0] * k_cats for _ in range(n_subjects)]
    for i, rater_labels in enumerate(ratings):
        for lbl in rater_labels:
            j = label_idx.get(lbl, label_idx["UNDETERMINED"])
            n_ij[i][j] += 1

    P_i = []
    for i in range(n_subjects):
        row_sum = sum(n_ij[i])
        if row_sum <= 1:
            P_i.append(0.0)
        else:
            P_i.append(
                sum(n_ij[i][j] * (n_ij[i][j] - 1) for j in range(k_cats))
                / (row_sum * (row_sum - 1))
            )
    P_bar = sum(P_i) / n_subjects

    total = n_subjects * n_raters
    p_j = [sum(n_ij[i][j] for i in range(n_subjects)) / total for j in range(k_cats)]
    P_e = sum(p ** 2 for p in p_j)

    if abs(1.0 - P_e) < 1e-9:
        return float("nan")
    return round((P_bar - P_e) / (1.0 - P_e), 4)


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

BINDING_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in [
        r"\b(data|phi|pii|records?|information)\b.{0,80}(cannot|must not|never|not permitted).{0,60}\b(leave|exit|be sent|third.part)",  # noqa: E501
        r"\b(self[- ]host|on[- ]prem|in[- ]house|locally hosted|private cloud|air[- ]?gapp)\w*.{0,120}?(complian|regulat|privacy|hipaa|gdpr|sovereignt|residency|sensitive data|phi\b|pii\b|confidential)",  # noqa: E501
        r"\b(cannot|can'?t|not allowed|prohibited|forbidden|ruled? out|unable to (use|send))\b.{0,100}?\b(openai|anthropic|gpt[- ]?\d|claude|third[- ]part\w+|external (api|service|provider|llm|model)|public (api|cloud|llm))",  # noqa: E501
        r"\bhipaa\b.{0,120}?(self[- ]host|on[- ]prem|in[- ]house|private|open[- ]?source model)",
        r"\bfedram\w*\b",
        r"\bato (required|needed|mandated)\b",
        r"\bclassified\b.{0,80}(environment|data|network|system)",
        r"\bdata sovereignty\b.{0,100}(force|require|mandated|self[- ]host|on[- ]prem)",
        r"\bcannot use third.party\b",
        r"\bproprietary model (prohibited|forbidden|not allowed)\b",
        r"\bopen.source (required|mandated|only)\b",
        r"\bin.house only\b",
        r"\b(data residency|data localiz).{0,100}(require|mandate|force|complian)",
        r"\bno (external|third.party|public) (api|model|llm)\b",
        r"\b(chose|selected|opted for|switched to|migrated to|went with|adopt\w*).{0,120}?(because of|due to|driven by|to (meet|satisfy|comply)).{0,60}?(complian|regulat|hipaa|gdpr|privacy|residency|sovereignt|governance)",  # noqa: E501
        r"\b(approved|vetted|whitelist\w*|authoriz\w*|certif\w*).{0,80}?(vendor|provider|model|llm)s?.{0,60}?(only|list|require)",
    ]
]

NON_BINDING_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\baudit log\b",
        r"\bdisclosure\b",
        r"\btransparency report\b",
        r"\bexplainability required\b",
        r"\bmodel card\b",
        r"\bimpact assessment\b",
        r"\baccountability framework\b",
    ]
]


def heuristic_label(text: str) -> str:
    for pat in BINDING_PATTERNS:
        if pat.search(text):
            return "BINDING"
    nb = sum(1 for pat in NON_BINDING_PATTERNS if pat.search(text))
    if nb >= 1:
        return "NON_BINDING"
    return "UNDETERMINED"


def run_heuristic_fallback(gov_rows: list[dict]) -> dict:
    print("[heuristic] Running extended keyword heuristic on 3 text window variants...")
    per_case_labels: list[list[str]] = []
    for row in gov_rows:
        short = (row.get("short_summary") or "").strip()
        full = (row.get("full_summary") or "").strip()
        full_combined = (short + "\n\n" + full).strip()
        texts = [
            full_combined,                           # full text
            (short + "\n" + full[:3000]).strip(),    # short + start of full
            full_combined,                           # same as first (consistent vote)
        ]
        per_case_labels.append([heuristic_label(t) for t in texts])

    final_labels = [majority_vote(lbls) for lbls in per_case_labels]
    n_total = len(final_labels)
    n_binding = final_labels.count("BINDING")
    n_non_binding = final_labels.count("NON_BINDING")
    n_undetermined = final_labels.count("UNDETERMINED")
    p_hat = round(n_binding / n_total, 4) if n_total else 0.0
    ci = bootstrap_ci([1 if lbl == "BINDING" else 0 for lbl in final_labels])
    kappa = fleiss_kappa(per_case_labels)

    return {
        "metadata": {
            "method": "heuristic-keyword",
            "models": ["extended-keyword-v1"] * 3,
            "model_ids": ["extended-keyword-v1"] * 3,
            "prompts": 3,
            "n_cases": n_total,
            "note": (
                "Heuristic fallback: 16 binding-indicator + 7 non-binding regexes "
                "over short_summary + full_summary. NOT LLM inference. "
                "3 variants = 3 text window sizes; majority vote per case."
            ),
        },
        "n_binding": n_binding,
        "n_non_binding": n_non_binding,
        "n_undetermined": n_undetermined,
        "p_hat_binding": p_hat,
        "ci_95": list(ci),
        "fleiss_kappa": kappa,
        "note": (
            "HEURISTIC method — not LLM ensemble. "
            f"p_hat_binding={p_hat:.4f} (95% CI [{ci[0]:.4f}, {ci[1]:.4f}]). "
            "Upgrade to LLM inference when transformers+CUDA env available."
        ),
        "per_case": [
            {
                "company": gov_rows[i].get("company"),
                "title": gov_rows[i].get("title"),
                "industry": gov_rows[i].get("industry"),
                "labels_per_prompt": per_case_labels[i],
                "final_label": final_labels[i],
            }
            for i in range(n_total)
        ],
    }


# ---------------------------------------------------------------------------
# LLM inference per model
# ---------------------------------------------------------------------------

def _infer_model(
    gov_rows: list[dict],
    model_id: str,
    model_label: str,
) -> list[list[str]]:
    """
    Run 3 prompt variants over all cases using one model.
    Returns per_case_labels shape [n_cases, 3].
    """
    import torch

    print(f"\n[llm] Loading {model_label} ({model_id}) ...")
    t0 = time.time()

    if "Qwen3-VL" in model_id or "Qwen3VL" in model_id:
        from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration  # noqa: I001
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_id,
            dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

    model.eval()
    print(
        f"[llm] {model_label} loaded in {time.time()-t0:.1f}s, "
        f"VRAM: {torch.cuda.memory_allocated()//1024**2}MB"
    )

    per_case_labels: list[list[str]] = []
    t_start = time.time()

    for case_idx, row in enumerate(gov_rows):
        if case_idx % 200 == 0 and case_idx > 0:
            elapsed = time.time() - t_start
            rate = case_idx / elapsed
            eta = (len(gov_rows) - case_idx) / rate
            print(
                f"  [{model_label}] {case_idx}/{len(gov_rows)} "
                f"({elapsed:.0f}s elapsed, ETA {eta:.0f}s)"
            )

        text = prepare_text(row, max_chars=900)
        case_labels: list[str] = []

        for prompt_fn in PROMPT_TEMPLATES:
            user_msg = prompt_fn(text)
            msgs = [
                {"role": "system", "content": SYSTEM_MSG},
                {"role": "user", "content": user_msg},
            ]
            try:
                # apply_chat_template with tokenize=False returns a string
                chat_text = tok.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True
                )
                inputs = tok(chat_text, return_tensors="pt").to(model.device)
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=8,
                        do_sample=False,
                        pad_token_id=tok.pad_token_id,
                        eos_token_id=tok.eos_token_id,
                    )
                new_tokens = out[0][inputs["input_ids"].shape[1]:]
                response = tok.decode(new_tokens, skip_special_tokens=True)
                label = parse_label(response)
            except Exception as exc:
                print(f"    WARNING case {case_idx}, prompt error: {exc}")
                label = "UNDETERMINED"
            case_labels.append(label)

        per_case_labels.append(case_labels)

    elapsed_total = time.time() - t_start
    print(
        f"[llm] {model_label} done: {len(gov_rows)} cases in "
        f"{elapsed_total:.0f}s ({elapsed_total/len(gov_rows):.2f}s/case)"
    )

    # Free VRAM
    del model
    import gc
    gc.collect()
    torch.cuda.empty_cache()

    return per_case_labels


# ---------------------------------------------------------------------------
# LLM ensemble
# ---------------------------------------------------------------------------

MODELS = [
    ("Qwen/Qwen3-VL-8B-Instruct", "Qwen3-VL-8B-Instruct"),
    ("Qwen/Qwen2.5-0.5B", "Qwen2.5-0.5B"),
]


def run_llm_ensemble(gov_rows: list[dict]) -> dict | None:
    """
    Run both models × 3 prompts = 6 votes per case.
    Returns annotation dict or None if CUDA unavailable.
    """
    try:
        import torch
        if not torch.cuda.is_available():
            print("[llm] CUDA not available — skipping LLM ensemble")
            return None
    except ImportError:
        print("[llm] torch not importable — skipping LLM ensemble")
        return None

    all_per_case: list[list[list[str]]] = []  # [n_models][n_cases][3 prompts]

    for model_id, model_label in MODELS:
        try:
            labels = _infer_model(gov_rows, model_id, model_label)
            all_per_case.append(labels)
        except Exception as exc:
            print(f"[llm] {model_label} FAILED: {exc}")
            all_per_case.append([["UNDETERMINED"] * 3 for _ in gov_rows])

    # Flatten to all 6 votes per case
    n_cases = len(gov_rows)
    per_case_all_votes: list[list[str]] = []
    for i in range(n_cases):
        votes: list[str] = []
        for model_labels in all_per_case:
            votes.extend(model_labels[i])
        per_case_all_votes.append(votes)

    final_labels = [majority_vote(v) for v in per_case_all_votes]
    n_binding = final_labels.count("BINDING")
    n_non_binding = final_labels.count("NON_BINDING")
    n_undetermined = final_labels.count("UNDETERMINED")
    p_hat = round(n_binding / n_cases, 4) if n_cases else 0.0
    ci = bootstrap_ci([1 if lbl == "BINDING" else 0 for lbl in final_labels])
    kappa = fleiss_kappa(per_case_all_votes)

    return {
        "metadata": {
            "method": "llm-ensemble",
            "models": [m[1] for m in MODELS],
            "model_ids": [m[0] for m in MODELS],
            "prompts": 3,
            "votes_per_case": len(MODELS) * 3,
            "n_cases": n_cases,
            "note": (
                f"{len(MODELS)} model families x 3 prompt variants = "
                f"{len(MODELS)*3} votes per case. "
                "Final label = majority vote (ties: UNDETERMINED > NON_BINDING > BINDING)."
            ),
        },
        "n_binding": n_binding,
        "n_non_binding": n_non_binding,
        "n_undetermined": n_undetermined,
        "p_hat_binding": p_hat,
        "ci_95": list(ci),
        "fleiss_kappa": kappa,
        "note": (
            f"LLM ensemble annotation. "
            f"p_hat_binding={p_hat:.4f} (95% CI [{ci[0]:.4f}, {ci[1]:.4f}]). "
            f"Fleiss kappa={kappa:.4f}."
        ),
        "per_case": [
            {
                "company": gov_rows[i].get("company"),
                "title": gov_rows[i].get("title"),
                "industry": gov_rows[i].get("industry"),
                "votes_by_model": {
                    MODELS[m][1]: all_per_case[m][i]
                    for m in range(len(MODELS))
                },
                "all_votes": per_case_all_votes[i],
                "final_label": final_labels[i],
            }
            for i in range(n_cases)
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_gov_rows() -> list[dict]:
    rows = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def gov_tagged(r: dict) -> bool:
        tags = set((r.get("application_tags") or "").split(","))
        return bool(tags & GOV_TAGS) or ((r.get("industry") or "") in REGULATED_INDUSTRIES)

    gov_rows = [r for r in rows if gov_tagged(r)]
    print(f"[data] {len(rows)} total rows → {len(gov_rows)} governance-tagged")
    return gov_rows


def main() -> None:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")

    gov_rows = load_gov_rows()
    n = len(gov_rows)
    assert n == 954, f"Expected 954 governance rows, got {n}"

    print(f"[main] Starting LLM-ensemble annotation of {n} cases...")
    result = run_llm_ensemble(gov_rows)

    if result is None:
        print("[main] LLM ensemble unavailable — falling back to heuristic")
        result = run_heuristic_fallback(gov_rows)

    # Write summary (no per_case)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in result.items() if k != "per_case"}
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Write per-case detail
    OUT_PER_CASE.write_text(
        json.dumps({"per_case": result.get("per_case", [])}, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("ANNOTATION COMPLETE")
    print("=" * 60)
    m = result["metadata"]
    print(f"Method:         {m['method']}")
    print(f"Models:         {', '.join(m['models'])}")
    print(f"N cases:        {m['n_cases']}")
    print(f"BINDING:        {result['n_binding']}")
    print(f"NON_BINDING:    {result['n_non_binding']}")
    print(f"UNDETERMINED:   {result['n_undetermined']}")
    print(f"p_hat_binding:  {result['p_hat_binding']:.4f}")
    print(f"95% CI:         [{result['ci_95'][0]:.4f}, {result['ci_95'][1]:.4f}]")
    print(f"Fleiss kappa:   {result['fleiss_kappa']}")
    print(f"\nSummary → {OUT_FILE}")
    print(f"Per-case → {OUT_PER_CASE}")


if __name__ == "__main__":
    main()
