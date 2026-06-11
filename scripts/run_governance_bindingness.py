"""E4 — does declared governance DISCRIMINATE among candidates? (node 6rb8dp)

Reviewer Q3: "Can you provide any evidence that declared governance constraints
discriminate among candidate configurations (i.e., would bind), rather than being
satisfied by all serious candidates?"

We scan the full text (short_summary + full_summary) of every governance-tagged
ZenML case study for explicit candidate-discriminating governance language:
phrases that name a configuration choice FORCED or EXCLUDED by a regulatory /
privacy / compliance requirement (self-hosting mandated, external APIs ruled
out, data-residency constraints, on-prem deployment for compliance, model choice
restricted to approved vendors, etc.). A case where governance merely *exists*
(the deployment is in a regulated industry) does NOT count; only language tying
the requirement to a configuration choice does.

This is keyword-pattern matching over the frozen snapshot — descriptive evidence
(counts + quoted examples), not a verdict input. Patterns are listed in-script
for auditability; matches are conservative (the count is a floor: paraphrases
that avoid every pattern are missed).

Outputs: outputs/p3/governance_bindingness.{json,md}

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_governance_bindingness.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

OUT_DIR = Path("outputs/p3")
SNAPSHOT = "data/zenml_llmops_snapshot.json"
PROVENANCE = "E4-governance-bindingness"

# Tags that bind governance in the published taxonomy.
GOV_TAGS = {"regulatory_compliance", "high_stakes_application",
            "content_moderation", "fraud_detection"}
REGULATED_INDUSTRIES = {"Healthcare", "Finance", "Legal", "Insurance",
                        "Government"}

# Candidate-discriminating governance language. Each pattern must tie a
# regulatory/compliance/privacy requirement to a CONFIGURATION choice
# (vendor/model/hosting selection or exclusion).
PATTERNS: dict[str, str] = {
    "self_host_or_onprem_required":
        r"(self[- ]host|on[- ]prem|in[- ]house|locally hosted|private cloud|"
        r"air[- ]?gapp)\w*[^.]{0,120}?(complian|regulat|privacy|hipaa|gdpr|"
        r"sovereignt|residency|sensitive data|phi\b|pii\b|confidential)",
    "compliance_forced_hosting":
        r"(complian|regulat|hipaa|gdpr|privacy|residency|sovereignt|phi\b|"
        r"pii\b)[^.]{0,120}?(self[- ]host|on[- ]prem|in[- ]house|private|"
        r"local(ly)? (deploy|host|run)|open[- ]?source model|open[- ]?weight)",
    "external_api_excluded":
        r"\b(could not|couldn'?t|cannot|can'?t|not allowed|prohibited|"
        r"forbidden|ruled? out|unable to (use|send)|never leaves?)\b"
        r"[^.]{0,100}?"
        r"\b(openai|anthropic|gpt[- ]?\d|claude|third[- ]part\w+|external "
        r"(api|service|provider|llm|model)|public (api|cloud|llm)|"
        r"cloud[- ]based (llm|model|api))",
    "data_cannot_leave":
        r"\b(data|phi|pii|records?|information)\b[^.]{0,80}?"
        r"\b(cannot|could not|must not|never|not permitted to|"
        r"isn'?t allowed to)\b"
        r"[^.]{0,60}?\b(leave|exit|be sent|be shared|go (to|outside)|"
        r"third[- ]part)",
    "approved_vendor_only":
        r"(approved|vetted|whitelist\w*|authoriz\w*|certif\w*)[^.]{0,80}?"
        r"(vendor|provider|model|llm)s?[^.]{0,60}?(only|list|require)",
    "compliance_drove_model_choice":
        r"(chose|selected|opted for|switched to|migrated to|went with|adopt\w*)"
        r"[^.]{0,120}?(because of|due to|driven by|to (meet|satisfy|comply))"
        r"[^.]{0,60}?(complian|regulat|hipaa|gdpr|privacy|residency|"
        r"sovereignt|governance)",
}


def main() -> None:
    rows = json.load(open(SNAPSHOT, encoding="utf-8"))

    def gov_tagged(r: dict) -> bool:
        tags = set((r.get("application_tags") or "").split(","))
        return bool(tags & GOV_TAGS) or (
            (r.get("industry") or "") in REGULATED_INDUSTRIES)

    gov_rows = [r for r in rows if gov_tagged(r)]
    pat = {k: re.compile(v, re.IGNORECASE | re.DOTALL) for k, v in PATTERNS.items()}

    hits: list[dict] = []
    per_pattern: dict[str, int] = dict.fromkeys(PATTERNS, 0)
    for r in gov_rows:
        text = " ".join([r.get("short_summary") or "", r.get("full_summary") or ""])
        matched = {}
        for name, p in pat.items():
            m = p.search(text)
            if m:
                per_pattern[name] += 1
                snippet = re.sub(r"\s+", " ", m.group(0))[:240]
                matched[name] = snippet
        if matched:
            hits.append({
                "company": r.get("company"), "title": r.get("title"),
                "industry": r.get("industry"),
                "source_url": r.get("source_url"),
                "matches": matched,
            })

    n_gov = len(gov_rows)
    n_hit = len(hits)
    res = {
        "metadata": {
            "provenance": PROVENANCE, "snapshot": SNAPSHOT,
            "n_total_rows": len(rows), "n_governance_tagged": n_gov,
            "patterns": PATTERNS,
        },
        "summary": {
            "n_governance_tagged": n_gov,
            "n_with_discriminating_language": n_hit,
            "fraction": round(n_hit / n_gov, 4) if n_gov else 0.0,
            "per_pattern": per_pattern,
        },
        "hits": hits,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "governance_bindingness.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E4 — candidate-discriminating governance language "
             "in ZenML case studies", ""]
    lines.append(f"- governance-tagged case studies: {n_gov}")
    lines.append(f"- with explicit candidate-discriminating governance language: "
                 f"**{n_hit}** ({100*n_hit/n_gov:.1f}%) — a floor "
                 "(conservative keyword patterns)")
    lines.append("")
    lines.append("| pattern | matches |")
    lines.append("|---|---|")
    for k, v in per_pattern.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Examples (first 8)")
    for h in hits[:8]:
        name, snip = next(iter(h["matches"].items()))
        lines.append(f"- **{h['company']}** ({h['industry']}): "
                     f"[{name}] “{snip}”")
    (OUT_DIR / "governance_bindingness.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"\nWrote {OUT_DIR/'governance_bindingness.json'} and .md")


if __name__ == "__main__":
    main()
