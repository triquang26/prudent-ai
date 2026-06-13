# PAPER_REVISION_NOTES.md — reframing diffs (Phase 3)

Editorial, load-bearing changes for `paper/paper.tex`. No new experiments — but the new
Tier-1 (calibrated transfer, `docs/PHASE1_RESULTS.md`) and Tier-3 (live loop,
`docs/PHASE2_RESULTS.md`) results give the paper a single clean arc. Some items below were
partly done in round-16/17 (noted inline); the rest are concrete diffs.

## 0. The one-sentence arc (the spine every section should serve)

> Diagnose the gap → **cure** the co-location part with calibrated transfer (guaranteed,
> partial) → **close the loop** on the measurable part with real acquisition → **name**
> precisely the governance part that needs new evidence.

One message, three moves, one clean boundary (curable-by-transfer / resolvable-by-measurement
/ structurally-unmeasured). Put this sentence at the end of §1 and mirror it in §8.

## 1. Split the two claims in the abstract

- **Primary (robust, no contested assumption):** the ecosystem **co-location gap** and the
  **binding mechanism** — most right-sizing decisions are underdetermined because evidence
  that exists is not co-located with the configurations that bind, and deciding anyway
  silently violates (57.1% blind-violation foil; imputation no-op; transfer recovers only a
  guaranteed minority).
- **Secondary (anchored, not assumed):** governance is **structurally unmeasured**, with the
  **OMB structured-field anchor (34.5% measured binding)** as the evidence — *not* the
  contested declared-implies-binding tag mapping.
- *Status:* round-16 already leads the abstract with the criterion-robust 56.9% / 47.3 pp
  structural number and demoted the binding sweep. **New diff:** add one clause that the
  governance binding is *measured* at 34.5% by OMB structured fields (ATO/PII/high-impact),
  independent of the deployed solution — moving OMB from support to headline evidence.

## 2. Promote OMB + Figure 8 (external-validity) into the main text

OMB measures governance from **structured machine-readable fields** (authority-to-operate,
PII, high-impact) *independently of the deployed solution* — so it simultaneously defuses
(a) publication self-selection and (b) the tag-imputation worry. It is currently in
Appendix~\ref{app:reviewer} / Appendix~\ref{app:binding_rate}; it is the **strongest**
governance evidence and should be a short main-text paragraph in §5 (the headline-scoped
block) plus the external-validity figure (`fig:extval`) promoted near it.

- **Diff (§5, after the "headline, scoped" paragraph):** add ~3 sentences: "Governance
  binding is not only declared but *measured*: on the US Federal AI Inventory, 34.5% of
  1,290 GenAI use-cases carry a structured governance-binding field (ATO/PII/high-impact),
  recorded independently of the chosen configuration (Appendix~\ref{app:binding_rate}).
  Because these are agency-reported schema fields, not our tag mapping, they neither inherit
  publication self-selection nor require the declared-implies-binding assumption."

## 3. Add the new arc — Tier-1 (transfer) + Tier-3 (loop)

A new subsection in §6 (procedure) or a short §6.x, with two results now in hand:

- **Calibrated transfer (Tier-1, guaranteed, partial).** "Replacing the point imputer with a
  *calibrated interval* predicted by cross-benchmark transfer and fed to the same verdict,
  the procedure commits only on a non-straddling interval and inherits
  P(infeasible | commit) ≤ α. On the masked-quality battery it recovers **24.9%** of
  co-location decisions at **0** observed violations (vs the point imputer's 53.3% blind
  violations and strict selective's 0% coverage), with the guarantee verified on held-out
  truth (coverage ≥ 1−α, feasibility-error 0.007/0.032/0.046 at α = .05/.10/.20). The other
  ~75% **correctly abstain** — transfer *certifies* they require measurement rather than
  recovering them." (Source: `docs/PHASE1_RESULTS.md`. Honest scope: partial; reaches only
  the measurable quality axis; refuses on structural axes by construction.)
- **Live acquisition loop (Tier-3, real).** "Closing the loop for real: an underdetermined
  query triggers the VoI-ranked measurement, whose value re-enters the substrate and the
  verdict re-runs. On 5 RouterBench slices the loop commits every decision with **0** hidden
  violations and **100% minimum-sufficient** commitments, in 1.0 probe (quality hidden) or
  2.0 probes (quality+cost hidden) — the simulated 2.0-vs-6.0 result now backed by a real
  closed loop. Governance is *not* loopable (no config↔audit data); the loop refuses rather
  than fake it." (Source: `docs/PHASE2_RESULTS.md`.)
- **Framing guard:** present transfer as "recovers a guaranteed minority, certifies the
  majority needs measurement" — this turns the Phase-0 NO-GO/PARTIAL into a positive that
  *strengthens* the thesis and motivates the loop. Do **not** overclaim recovery.

## 4. Compress §5 + robustness appendices (number-saturation)

The review flagged density. Move the encyclopedic ablations in Appendix~\ref{app:reviewer}
into a **single robustness table** (one row per ablation: knob, range, headline-stays-≥).
Keep in-text only: confidence policy, taxonomy single-drop, query-distribution (incl.
negative-control 12.4%), joint-drop floor, independent-corpus replication. Everything else
(cost-threshold sensitivity, completion-semantics, acq-cost perturbation, verdict-mechanics)
becomes table rows with a one-line caption, not prose paragraphs.

- *Status:* round-16 already trimmed the abstract/§5; this item is the **appendix** compression,
  still to do. Target: one `robustness summary` table replacing ~6 prose paragraphs.

## 5. Tone fix — B2 baseline name

Rename B2 from "the community's honest default" to **"automated-tooling default"** (a tool
that ranks on visible axes and treats missing-as-satisfied), to avoid the strawman objection
that no careful human would commit blind.

- *Status:* round-16 changed it to **"pre-measurement default"** in §1/§6. **Decide:**
  "automated-tooling default" is the spec's wording and is sharper about *what* commits blind
  (a tool, not a person). Recommend switching the remaining "pre-measurement default"
  mentions to "automated-tooling default" for consistency with the rebuttal framing.

## 6. Caveat the categorical-gate magnitudes

Present the multi-gate governance harm as a **mechanism** claim, not a measured governance
property:

- **Diff (§6 governance paragraph / Appendix multigate):** "We read min(HVR) = **8.0% > 0**
  across the three gates as the *mechanism* result — blind commitment harms regardless of
  which governance gate is operative. The *magnitude* (8.0%–45.3%) is a function of the
  admissible-set size of each constructed gate (2/11 admissible for G3 vs 8/11 for G2), not a
  measured property of real governance, which remains unmeasured. The categorical gate is a
  bridge that the mechanism operates on a governance-shaped constraint, not an estimate of
  real governance harm."

## 7. Where each change lands (quick index)

| Change | Section/label | Status |
|---|---|---|
| Abstract: primary/secondary split + OMB-as-evidence clause | abstract | partial (16) + new clause |
| OMB + fig:extval to main text | §5 (`sec:map`) | new |
| Tier-1 transfer + Tier-3 loop subsection | §6 (`sec:method`) | new (results ready) |
| Arc sentence | end §1, mirror §8 | new |
| Robustness → single table | Appendix~\ref{app:reviewer} | new |
| B2 → "automated-tooling default" | §1/§6 | switch from round-16 wording |
| Categorical-gate magnitude caveat | §6 / multigate appendix | new |

**Note on page budget:** adding the Tier-1/Tier-3 subsection (~0.4 page) must be offset by the
§5/appendix compression (item 4) and the robustness-table consolidation to hold the 9-page
main-text limit. Verify `grep sec:limitations paper.aux → {9}` and 0 overfull after edits.
