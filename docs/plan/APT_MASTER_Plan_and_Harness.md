# APT — MASTER PLAN & HARNESS (consolidated, detailed)
# Evidence-Decidability of AI Deployment Right-Sizing + Value of Information

> **Tài liệu master.** Hợp nhất & thay thế: Research_Plan, Phase_Harness (MVP), Oral_Plan v1/v2,
> ICLR_framing addendum. Dùng làm bản keep duy nhất; dán vào chat mới để khôi phục toàn bộ context.
> **Không code** (planning + formalism level). *Pham Tri Quang · CS197 · target: ICLR / NeurIPS-ED 2027 cycle · 2026-06*

## MỤC LỤC
- **Phần I — Chiến lược & Thesis** (§1–§4)
- **Phần II — Formalism** (§5–§11) ← spine, mức paper
- **Phần III — Ràng buộc toàn cục** (§12)
- **Phần IV — Data** (§13)
- **Phần V — Baseline lattice** (§14)
- **Phần VI — HARNESS 7 PHASE chi tiết** (§15)
- **Phần VII — Evaluation** (§16)
- **Phần VIII — Model-paper maps** (§17)
- **Phần IX — Reviewer-attack & Go/No-Go** (§18)
- **Phần X — References đã verify** (§19)

---
# PHẦN I — CHIẾN LƯỢC & THESIS

## §1. Thesis (một câu) + 3 Claims
**Thesis:** *Bằng chứng evaluation hiện có không chỉ thiếu; nó khiến nhiều quyết định **right-sizing khi triển
khai trở nên evidence-underdetermined (không nhận dạng được từ bằng chứng)**. Khi người ta vẫn trả lời bằng
leaderboard accuracy/cost, họ **mis-size hệ thống một cách đo được**.*

| Claim | Phát biểu | Chứng bằng | Trục |
|---|---|---|---|
| **C1** (measuring) | Trên phân phối query triển khai thực, nhiều quyết định right-sizing **không evidence-decidable**, do **missingness có cấu trúc** (không ngẫu nhiên). | Decidability map (P3) | **cả 8** |
| **C2** (x>y, gây đau) | Decision rule kiểu leaderboard **vẫn trả lời** các query đó → **decision regret** + **hidden constraint violation** đo được. | Validation V1 (P5) | **4 đo được** |
| **C3** (method) | Selective procedure 3-state + **VoI** + **coverage guarantee**: không chỉ nói "không biết" mà nói **đo field nào tiếp** để giảm regret, và **chỉ commit khi đảm bảo đúng ≥ 1−α**. | Procedure (P4) + Validation V2 (P5) | 4 đo được |

## §2. Dual-venue framing (chốt SỚM — gate ở P0)
Cùng một core (substrate + decidability map + procedure + validation). Đổi **ngôi sao** + **model paper** theo venue. **Không viết bài Frankenstein làm cả hai.**

| | **NeurIPS Evaluations & Datasets** | **ICLR** |
|---|---|---|
| Ngôi sao | **Decidability measurement** (evaluation as object of study) | **Method**: selective right-sizing + guarantee + **limit theorem** |
| Hook | "evidence khiến right-sizing underdetermined; ta đo tần suất + chỉ ra blind spots" | "selective decision dưới evidential uncertainty *có guarantee*; evidence chỉ-leaderboard *về nguyên tắc không* right-size được" |
| Model paper | HAL, JudgeBench | Trust or Escalate (#1), Limits to scalable evaluation (#2) |
| Áp lực x>y | thấp ("need not outperform") | cao — cần guarantee + empirical gây đau + theorem |
| Rủi ro chính | "missing is obvious" | "theorem đủ sâu?" + "guarantee novel hơn selective classification?" |
| Cần theory collaborator? | không | **có thể**, cho limit theorem (§11) |

## §3. Điều gì làm nên Oral (không phải cái gì)
- ❌ relational DB + nhiều row → resource, không bất ngờ. ❌ min-cost rule → constrained selection kinh điển. ❌ "benchmark thiếu metric" → đúng nhưng nhàm.
- ✅ Oral = giao điểm **reframe sắc (underdetermined/non-identifiable)** × **measurement bất ngờ (C1)** × **validation thắng baseline (C2/C3)** × (ICLR) **limit theorem + guarantee**.

## §4. Positioning vs hàng xóm (mỗi cái một câu)
- **HELM** (2211.09110): holistic multi-metric *per-model* → là **evidence input**, không phải decision procedure.
- **HAL** (2510.11977): đo agent chuẩn hơn, cost-aware (21,730 rollouts, ~$40k) → *threat gần nhất*; bạn hỏi **khi nào kết luận deployment hợp lệ về bằng chứng**.
- **AI Agents That Matter** (2407.01502): accuracy-only gây hiểu lầm → joint accuracy+cost. Bạn vượt: accuracy/cost-only **vẫn trả lời query đáng lẽ phải abstain** vì thiếu latency/energy/governance.
- **FrugalGPT** (2305.05176, 98% cost↓) / **LLMSelector** (2502.14815, +5–70%): tối ưu dưới objective *đã quan sát*; bạn quyết định dưới evidence **thiếu + bất định**.
- **Trust or Escalate** (ICLR'25 Oral): selective eval + guarantee P(agree|evaluate)≥1−α → model paper cho **method/guarantee**.
- **Limits to scalable evaluation** (ICLR'25 Oral): shortcut→limit theorem→empirical → model paper cho **Pillar limit**.

---
# PHẦN II — FORMALISM (spine, mức paper)

## §5. Objects & ký hiệu
- Task archetype `τ ∈ T`. Composition (AI Box) `x ∈ X` = assembly có cấu hình của các component.
- **8 trục right-sizing** `A = {quality, latency_p95, throughput, cost, energy, memory/hw, governance, reviewer_burden}`.
  Phân hoạch: **đo được** `A_m = {quality, cost, latency, energy}` (có ground truth); **khó quan sát** `A_h = {governance, reviewer_burden, ...}`.
- Giá trị thật `θ_a(x)` (KHÔNG quan sát trực tiếp). **Evidence corpus** `E` = tập evidence item, mỗi cái nối `(x, a)` tới một giá trị + source + confidence, hoặc thiếu.
- **Belief evidential** `B_E(x,a) ∈ {⊥} ∪ Δ(ℝ)`: hoặc `⊥` (không có bằng chứng / missing), hoặc một phân phối/khoảng trên giá trị khả dĩ (uncertainty từ nhiều nguồn + confidence).

## §6. Bài toán right-sizing có ràng buộc (oracle, full info)
Query `q = (τ, c)`, ràng buộc cứng `c`: `quality ≥ q*`, `latency_p95 ≤ L*`, `hardware ∈ H`, `governance ⊇ G`, `privacy = P`, `human_review = R`. Mục tiêu: min cost.
> **x\*(q) = argmin₍ₓ ∈ X : feasible(x,c)₎ cost(x)** — *minimum-sufficient configuration* dưới giá trị thật `θ`.

## §7. Ba trạng thái feasibility (dưới quan sát thiếu) — formal
Với candidate `x`, ràng buộc `c`, corpus `E`, risk `α`:
- **provably-feasible:** mọi hard constraint certify được từ `B_E` — vd `P_{B_E}(quality(x) ≥ q*) ≥ 1−α`, các ràng buộc categorical (hw/gov/privacy/review) certify ✓, và **không field bắt buộc nào = ⊥**.
- **provably-infeasible:** ∃ hard constraint certify *vi phạm* — vd `P_{B_E}(latency(x) ≤ L*) < α`, hoặc categorical fail.
- **possibly-feasible (pending field f):** không certify được cả hai chiều vì ≥1 field bắt buộc `f` có `B_E(x,f)=⊥` hoặc quá bất định. **Trả về tập field chặn `f`.**

## §8. Evidence-decidability / Non-identifiability — formal (neo của C1)
Gọi `Comp(E)` = tập các "completion" của E (mọi cách điền giá trị cho field ⊥/bất định, *nhất quán* với E).
- Query `q` **evidence-decidable dưới E** ⇔ tồn tại `x` provably-feasible mà `argmin cost` **bất biến** trên mọi `completion ∈ Comp(E)` — tức quyết định tối ưu **được nhận dạng** bởi E.
- `q` **evidence-underdetermined dưới E** ⇔ quyết định minimum-sufficient **non-identifiable**: `∃ e₁, e₂ ∈ Comp(E)` cho `x*(q|e₁) ≠ x*(q|e₂)`. Tương đương: **∃ field thiếu mà giá trị của nó *lật* argmin.**
> Đây là điểm mới so với HAL/HELM: họ cải thiện `B_E`; bạn nghiên cứu **khi nào E đủ để nhận dạng quyết định**.

## §9. Selective right-sizing + Coverage guarantee (neo của C3; style Trust-or-Escalate)
Procedure trả về: **(i)** recommendation commit `x̂(q,E)`, hoặc **(ii) ABSTAIN** + tập field chặn + gợi ý đo theo VoI.
- **Guarantee (distribution-free):** cho risk `α` người dùng đặt, tập commit `C` thỏa
  > **P( x̂ feasible ∧ x̂ minimum-sufficient | q ∈ C ) ≥ 1 − α**
  calibrate bằng fixed-sequence testing / conformal trên **ground-truth slice**. **Coverage** = `|C| / |queries|`; report **coverage–risk tradeoff** (như Trust-or-Escalate report coverage ở mức agreement).
- **Delta novelty** (chống "chỉ port selective classification"): object là **quyết định đa-ràng-buộc dưới missingness** (feasibility ∧ min-sufficiency *đồng thời*), khó hơn selective *binary* classification; guarantee gắn **evidence regime** không phải sample size.

## §10. Value of Information (làm abstention "thông minh")
Với `q` dưới `E` có field chặn/bất định, decision loss (regret) `L(x̂) = max(0, cost(x̂) − cost(x*)) + λ·violation(x̂)`.
> **VoI(f) = E[ L(x̂_E) ] − E₍quan sát f₎[ L(x̂_{E∪{f}}) ]** — kỳ vọng giảm regret khi đo field `f`.
- Abstention gợi ý đo `argmax_f VoI(f)`. **Cost-aware:** xếp theo `VoI(f) / cost(đo f)` — song song "Cascaded Selective Evaluation" (rẻ trước, trả tiền đo trục đắt chỉ khi đáng).
- *Đây là chỗ bạn vượt Trust-or-Escalate:* abstention của bạn **chỉ ra phải đo gì**, không chỉ "không trả lời".

## §11. Limit theorem (Pillar ICLR — CAO NHẤT & RỦI RO NHẤT; style Limits-to-scalable-eval)
- **Evidence regime** `R ⊆ A` = tập trục mà E *có bất kỳ* bằng chứng (vd `R = {quality, cost}`). Rule là **R-restricted** nếu chỉ phụ thuộc `B_E` giới hạn trên `R`.
- **Statement (informal, cần chứng minh):** Với class query `Q_R` mà **binding constraint nằm trên trục `a ∉ R`**, *không* R-restricted rule nào đạt expected regret dưới một bound dương `Δ(R)` — buộc phải hoặc **(a)** commit và mis-size (regret/violation) trên một phần không đổi của `Q_R`, hoặc **(b)** abstain toàn bộ `Q_R`.
  > Slogan song song: *"Accuracy/cost evidence won't beat measuring the binding axis"* (≈ "won't beat twice the data").
- **Intuition (indistinguishability/identifiability):** dựng hai "thế giới" trùng nhau trên `R` nhưng khác trên `a ∉ R`, với optimum khác nhau; mọi R-restricted rule không phân biệt được → sai ở ít nhất một.
- **Empirical confirmation:** trên ground-truth slice, mis-sizing thực của leaderboard rule **còn tệ hơn** `Δ(R)` (do tương quan/heavy-tail cost–latency–energy).
- ⚠️ **Honest flag:** nếu theorem không chứng minh được *sạch & không tầm thường* → **bỏ Pillar này, lùi NeurIPS-ED** (measurement-as-thesis không cần theorem). Cân nhắc theory collaborator ngay ở P0.

---
# PHẦN III — RÀNG BUỘC TOÀN CỤC

## §12. C1–C8 (không phase nào vi phạm)
| # | Constraint |
|---|---|
| C1 | **Không bịa số.** Cost/latency/energy/burden không nguồn ⇒ `estimated` + giả định; KHÔNG dùng cho claim. |
| C2 | **Provenance + uncertainty bậc nhất.** Mọi thuộc tính = {value, confidence, evidence_id, is_missing, source_type}. Không "điểm trần trụi". |
| C3 | **Snapshot có version + reproducibility.** Đóng băng corpus; re-extract phải log. (ED-track nhấn RAI metadata + repro.) |
| C4 | **Confidence protocol §5.2 (brief).** high/medium/low; query mặc định high+medium; low chỉ opt-in. |
| C5 | **Review chéo + IAA.** `reviewed_by_human` chỉ khi người thứ 2 xác nhận; báo **κ**. |
| C6 | **Giữ ngữ cảnh so sánh.** metric name/direction/unit/dataset/split/hardware luôn giữ. |
| C7 | **Tách substrate ⟂ solver.** SQL chỉ retrieve+filter baseline; tối ưu/VoI/guarantee ở tầng solver tách rời. |
| C8 | **Mọi claim falsifiable + no leakage.** Validation slice KHÔNG dùng tune procedure. |

---
# PHẦN IV — DATA

## §13. 12–20 nguồn, phủ đúng 4 regime (versioned + κ); đuôi dài → references-only
| Regime | Nguồn lõi (ingest) | Vai trò | Link |
|---|---|---|---|
| **R1 model-quality** | HELM Classic/Capabilities/Lite | quality (+ efficiency một phần) — evidence input | crfm.stanford.edu/helm (2211.09110) |
| **R2 agent+cost** | **HAL** · AI Agents That Matter · BFCL v4 | composition + **$ đo thật** → validation slice | hal.cs.princeton.edu (2510.11977) · 2407.01502 · gorilla.cs.berkeley.edu/leaderboard |
| **R3 serving/latency** | MLPerf Inference v5.0/5.1/6.0 · vLLM | latency p50/p95, throughput, hardware tier | github.com/mlcommons/inference · SOSP'23 |
| **R4 energy** | **ML.ENERGY** | energy J/task (H100/vLLM) → validation slice | ml.energy/leaderboard (2505.06371) |
| +routing | RouterBench | cost records → validation slice | 2403.12031 |
| +retrieval (tùy) | BEIR / KILT | retrieval quality cho RAG composition | beir-cellar/beir · facebookresearch/KILT |
| **Query dist + governance blind-spot** | ZenML LLMOps DB · MedHELM | phân phối query *thật* + bằng chứng governance/burden vắng | zenml.io/llmops-database · 2505.23802 |

**Tách trục (quan trọng):** decidability map (C1) dùng **cả 8 trục** *vì governance/burden là blind spot tệ nhất*; x>y validation (C2/C3) chỉ chạy **4 trục đo được** nơi có ground truth.
**Extraction tooling (paper-rows, chỉ semi-auto + review + κ):** GROBID (PDF→TEI) · MOLE (2505.19800, ~67%) · AXCELL (2020.emnlp-main.692, F1 25.8).

---
# PHẦN V — BASELINE LATTICE

## §14. B1–B6 (thắng B2 & B3 thì claim cứng)
| | Baseline | Mô tả | Ý nghĩa |
|---|---|---|---|
| B1 | accuracy-only ranking | accuracy cao nhất "đủ nhỏ" | strawman — không đứng một mình |
| **B2** | **observed-metrics Pareto** | Pareto chỉ trên field có sẵn, lờ missingness | **thực hành trung thực hiện tại — BẮT BUỘC thắng** |
| **B3** | **imputation** (mean/median + model-based) | điền field thiếu rồi quyết | phòng thủ "cứ điền đại" — **phải thắng** |
| B4 | missing-as-fail (conservative) | field thiếu = vi phạm | cận trên bảo thủ: 0 hidden-violation, abstain cao |
| B5 | oracle-full-evidence | biết hết field | **sàn regret** — "về nguyên tắc cứu được bao nhiêu" |
| B6 | HAL/FrugalGPT cost-accuracy frontier | tối ưu accuracy+cost, bỏ latency/energy/gov | đối thủ domain — show vi phạm trục bị bỏ |

**Claim cứng khi:** `regret(proc) < regret(B2)` và `< regret(B3)`; `hidden-violation(proc) ≪ hidden-violation(B2,B6)`; `regret(proc + top-VoI) → regret(B5)`; và **VoI lift**: đo top-VoI giảm regret > đo random.

---
# PHẦN VI — HARNESS 7 PHASE (chi tiết)

## §15. Cấu trúc mỗi phase: Mục tiêu · Bài toán · I/O · Constraints(cứng/scope/data) · Data+link · Paper+lý do · Test(eng/research) · ICLR-upgrade · Gate · Rủi ro · Feed-paper

### P0 — Formalize + chốt venue (spine · ~3–5 tuần)
- **Bài toán:** viết §5–§11 (formalism) đủ chặt để *đẻ ra* measurement (P3) + procedure (P4) + (ICLR) theorem. Chốt venue + model paper.
- **I/O:** in = brief + nearest neighbors; out = formalism + **intro 6 đoạn** + model paper + (ICLR) *statement* theorem + quyết định theory collaborator.
- **Constraints:** *cứng* mọi định nghĩa falsifiable (C8), claim shape rõ; *scope* chưa code/extraction; *data* định nghĩa uncertainty model TRƯỚC khi thu (để extraction ghi đúng thứ formalism cần).
- **Data/paper:** model paper = HAL/AIATM (NeurIPS-ED) hoặc Trust-or-Escalate/Limits (ICLR); đọc để map cấu trúc.
- **Test:** formalism có suy ra được decidability map + VoI? intro có hook "underdetermined" + claim x>y validate được?
- **ICLR-upgrade:** thêm *mục tiêu theorem* (§11) + *định nghĩa guarantee* (§9). **Gate đi/không-đi ICLR:** có chứng minh được statement sơ bộ / có collaborator không?
- **Gate:** prof duyệt formalism *novel-and-correct*; intro 6 đoạn; venue + model paper chốt.
- **Rủi ro:** over-formalize. Mitigate: formalism phải đẻ ra measurement+method, không trang trí.
- **Feed-paper:** §3 Problem Formulation = trái tim.

### P1 — Evidential substrate (resource · ~4–6 tuần)
- **Bài toán:** substrate sao cho mỗi thuộc tính mang **{distribution/interval, confidence, evidence_id, is_missing}** và **composition là đơn vị bậc nhất**; substrate *đỡ* solver (P4), không chỉ trả SELECT.
- **Vì sao SQL/relational (câu hỏi về prof):** (1) composition cần normalization + component reuse + lineage (flat table không diễn được); (2) **FK = auditability claim ở dạng thực thi** (referential integrity *là* guarantee provenance = ∃x); (3) missingness = NULL-semantics → reportability map là query; (4) SQLite zero-config, demo offline. **C7:** SQL chỉ substrate+baseline; solver tách rời.
- **I/O:** in = formalism + 1 nguồn seed; out = schema cho phép {dist, interval, ⊥} per axis + observation-uncertainty layer; interface cố định `substrate → candidate set (mỗi thuộc tính kèm uncertainty+evidence)`; data dictionary.
- **Constraints:** *cứng* FK đầy đủ (C2), interface bất biến (C7); *scope* design-for-extension nhưng đủ chạy; *data* seed HELM Lite.
- **Test:** interface cho phép thay solver (lexicographic→chance-constrained→selective) *không đổi substrate*? một thuộc tính giữ được *nhiều observation + uncertainty*?
- **Gate:** substrate khởi tạo; interface cố định; baseline query (Appendix E) chạy; dictionary commit.
- **Rủi ro:** trượt thành "DB engineering". Mitigate: substrate là *để đỡ solver*.
- **Feed-paper:** §4 System.

### P2 — Scoped extraction 12–20 nguồn / 4 regime (~5–7 tuần)
- **Bài toán:** phủ đủ rộng để measurement đại diện, với QC đo được (κ + error rate).
- **I/O:** out = substrate populated trên 4 regime; **IAA/κ + extraction error rate** report; coverage log {pattern × axis × source_type × confidence}.
- **Constraints:** *cứng* paper-rows chỉ semi-auto + review (C1/C4) — *bằng chứng: AXCELL F1 25.8, MOLE ~67%, compute thiếu 60–89%, 3/24 reproducible*; *scope* leaderboard ưu tiên, đuôi dài references-only; *data* dừng mở rộng sau phase (C3).
- **Test:** κ giữa 2 annotator? precision trên mẫu vàng? coverage *bão hòa* ở ~15–25 nguồn chưa?
- **Gate:** 4 regime đủ data; κ + error rate; coverage saturate.
- **Rủi ro:** extraction noise hỏng finding. Mitigate: tách reported/estimated/measured; chỉ high+medium cho claim.
- **Feed-paper:** §4 Data + Appendix Extraction-quality.

### P3 — Decidability map (finding · cả 8 trục · ~4–6 tuần)
- **Bài toán:** định lượng *right-sizing trả lời được tới đâu*: % query **evidence-decidable / underdetermined / infeasible** theo {archetype × evidence regime × confidence}; đặc tả **structural blind spots**.
- **I/O:** out = decidability map + blind-spot characterization (kỳ vọng energy/governance/burden/on-prem cost) + thống kê **CI + sensitivity**.
- **Constraints:** *cứng* query distribution **justify từ ZenML/MedHELM thật**, không cherry-pick (C8); finding bền sensitivity trên confidence threshold & uncertainty model.
- **Test (thesis):** H1 phần lớn query thực *underdetermined*; H2 blind spots *có hệ thống* theo axis; H3 bền sensitivity.
- **ICLR-upgrade:** decidability map = **empirical confirmation** cho limit theorem (§11).
- **Gate:** map + blind-spot + CI; finding sống sót sensitivity; prof thấy "bất ngờ-đủ".
- **Rủi ro (lớn nhất cho Oral):** finding "hiển nhiên". Mitigate: đẩy từ "% missing" → "% *decisions* underdetermined" + "thực hành *mis-size* đo được" (P5).
- **Feed-paper:** §5 Findings.

### P4 — Selective procedure + guarantee + VoI (method · ~5–7 tuần)
- **Bài toán:** triển khai §7–§10: 3-state feasibility + **chance-constrained/robust** + **coverage guarantee** (calibrate trên slice) + **VoI ranking** + Pareto-under-uncertainty; mọi output **auditable + explainable**.
- **I/O:** out = procedure (≥2 variant) + VoI module + guarantee calibration + Pareto-under-uncertainty.
- **Constraints:** *cứng* đọc qua interface P1 (C7); phân biệt tầng với Circinus/Cascadia (runtime serving — bạn pre-deployment evidential); *scope* không cần online serving.
- **Test:** trả đúng 3 trạng thái? guarantee giữ ở coverage cao? VoI *dự đoán* được field đáng đo (validate P5)? Pareto-under-uncertainty ổn định?
- **ICLR-upgrade:** đây là **method-as-star** của ICLR — selective right-sizing với guarantee + VoI-guided acquisition cascade.
- **Gate:** procedure + VoI + guarantee chạy, output có explanation; coverage–risk curve dựng được.
- **Rủi ro:** bị xem "chance-constrained opt dán nhãn". Mitigate: novelty ở **VoI cho right-sizing trên evidential substrate** + 3-state + abstention informative, không ở solver.
- **Feed-paper:** §6 Method.

### P5 — VALIDATION (trụ Oral · 4 trục đo được · ~5–8 tuần)
- **Bài toán:** chứng minh procedure *đúng* + practice hiện tại *sai đo được*, trên slice **có ground truth**.
- **V1 (core):** mask 1 trong 4 trục đo được → predict minimum-sufficient → so **regret + hidden-violation** với **lưới B1–B6** trên HAL/BFCL/RouterBench/ML.ENERGY.
- **V2 (core):** đo field **top-VoI** → giảm regret > đo random? recommendation đổi đúng VoI dự báo? **+ coverage–risk:** guarantee giữ ở coverage cao (như Trust-or-Escalate).
- **V3 (stretch, optional):** chạy thật vài AI Box cục bộ (vLLM + đo energy chuẩn ML.ENERGY + human study nhỏ cho governance/burden) trên 1–2 archetype (clinical-summarization HIPAA; web-navigation).
- **Constraints:** *cứng* slice **không** dùng tune procedure (C8 leakage); mọi x>y có **significance**; *data* HAL/BFCL/RouterBench/ML.ENERGY/ZenML + (V3) open models, BEIR/KILT, MEDRAG (MIRAGE 2402.13178).
- **Test (quyết định Oral):** procedure thắng B2,B3 có ý nghĩa? VoI đúng? (V3) missingness-uncertainty đổi quyết định?
- **Gate:** V1+V2 thắng B2,B3 có significance; coverage–risk curve; (V3 nếu có tài nguyên).
- **Rủi ro (sống còn):** baseline accuracy-only/Pareto *không thua* → finding yếu. Mitigate: chọn slice nơi đa trục **thực sự bind** (energy/latency-bound, on-prem).
- **Feed-paper:** §7 Evaluation — trụ chính.

### P6 — Write / ablation / rebuttal-proof / talk (~4–6 tuần)
- **Bài toán:** ráp paper theo model paper đã chọn; ablation; threats; repro package + RAI metadata; talk.
- **Constraints (chuẩn nghiệm thu):** repro clean-checkout + snapshot; ablation theo **evidence regime** (accuracy-only→+cost→+energy→full), uncertainty model, confidence threshold, α; threats §16; talk: 1 hook (underdetermined) / 1 figure (decidability map) / 1 kết quả (V1 x>y) / 1 forward (VoI).
- **Test:** outsider "get" hook trong 2 phút? mọi claim falsifiable + có số? ablation cô lập *vì sao* procedure thắng?
- **Gate:** paper full + ablation + repro + talk; **mock review ≥ ngưỡng Oral**.
- **Rủi ro:** viết tốt mà thiếu reframe/validation → tụt poster. Mitigate: §18 Go/No-Go.
- **Feed-paper:** toàn bộ.

---
# PHẦN VII — EVALUATION

## §16. Constructs (reviewer Oral soi kỹ)
| Construct | Định nghĩa |
|---|---|
| **DV1 decidability** | % query (task×constraint) evidence-decidable / underdetermined / infeasible dưới E |
| **DV2 decision regret** | cost overshoot của recommendation vs true minimum-sufficient (ground-truth slice) |
| **DV3 hidden-violation rate** | % baseline *âm thầm* vi phạm latency/energy/governance |
| **DV4 coverage–risk** | coverage đạt được ở mức guarantee 1−α (selective) |
| **DV5 VoI lift** | giảm regret khi đo top-VoI vs random |
| **IV** | evidence regime (accuracy-only→+cost→+energy→full) · confidence threshold · uncertainty model · α · task archetype |
| **Baselines** | B1–B6 (§14) |
| **Threats** | extraction bias (κ, error rate) · query-distribution bias (justify từ ZenML/MedHELM) · hardware confounder (energy H100-only) · selection bias nguồn · **leakage** (slice không tune) |

**Map claim → proof:** C1 ← DV1 (P3, 8 trục) · C2 ← DV2+DV3 (P5 V1, 4 trục, vs B2/B3) · C3 ← DV4+DV5 (P4+P5 V2).

---
# PHẦN VIII — MODEL-PAPER MAPS (reverse-outline)

## §17.1 Trust or Escalate (ICLR'25 Oral; 2407.18370) → của bạn
problem: judge tin dùng vô điều kiện → leaderboard tin dùng vô điều kiện để right-size ·
insight: confidence + selectively trust, P(agree|evaluate)≥1−α → evidence-sufficiency + selectively commit, P(feasible∧min-sufficient|commit)≥1−α ·
mech: Simulated Annotators (calibration) + fixed-sequence testing + Cascaded (cheap→strong judge) → evidence-uncertainty per-axis + calibrate trên ground-truth slice + **VoI-guided acquisition cascade** ·
abstention: không evaluate khi không tự tin → **abstain = đo field top-VoI** (informative) ·
proof: agreement cao ở coverage cao, model rẻ → guarantee giữ ở coverage cao; baseline vi phạm; VoI→oracle.

## §17.2 Limits to scalable evaluation (ICLR'25 Oral; NO6Tv6QcDs) → của bạn
shortcut: debias bằng vài nhãn thay nhiều → leaderboard (accuracy/cost) thay đo mọi trục ·
**theorem:** judge không hơn model bị đánh giá ⇒ không giảm nhãn quá ½ → regime R thiếu trục bind ⇒ không R-rule nào giảm mis-sizing dưới Δ(R) ·
empirical: tiết kiệm thực còn tệ hơn bound → mis-sizing thực còn tệ hơn Δ(R) ·
area: learning theory → identifiability/decision theory under partial observation.

**Model paper phụ (reviewer gợi):** HAL (infra+cost-aware), JudgeBench (benchmark phơi reliability failure), SKILL-MIX ("leaderboards miss the construct").

---
# PHẦN IX — REVIEWER-ATTACK & GO/NO-GO

## §18.1 Đòn reviewer + phòng thủ
| Đòn | Phòng thủ |
|---|---|
| "Missing metrics is obvious." | Surprise ở **C2: rule cộng đồng trả lời bừa và mis-size đo được** trên slice kiểm chứng được. |
| "'Undecidable' quá đà." | Đã đổi → **non-identifiability / evidence-underdetermined** (§8), neo thống kê. |
| "Chỉ chance-constrained opt dán nhãn." | Novelty ở VoI trên evidential substrate + 3-state + decidability *measurement*. |
| "Imputation giải quyết được." | **B3**: imputation tạo hidden-violation/regret cao hơn (overconfident trên missingness có cấu trúc). |
| "Guarantee chỉ port selective classification." | Delta §9: object đa-ràng-buộc dưới missingness; abstention informative (VoI); guarantee theo evidence regime. |
| "Limit theorem tầm thường." | Nếu không sạch → **rớt NeurIPS-ED** (không cần theorem). |
| "HAL đã làm." | HAL = đo chuẩn hơn; bạn = *khi nào kết luận hợp lệ về bằng chứng*. Model paper #3 *và* threat. |
| "Không deployment thật." | Guarantee + empirical trên ground-truth slice (V1/V2) đủ; V3 stretch. |
| "Governance/burden không validate." | Đó *là* finding C1: vắng tới mức không kiểm chứng → quyết định bind vào chúng underdetermined. Validation chỉ 4 trục đo được. |

## §18.2 Go / No-Go (thành thật)
- P3 chỉ "missing nhiều" mà **P5 không chứng minh mis-sizing** (B2/B3 không thua có ý nghĩa) → **KHÔNG ép Oral**; nộp main/Negative-Results hoặc ED poster.
- ICLR: theorem không sạch **và** guarantee không novel hơn baseline → **nộp NeurIPS-ED**.
- Oral = giao điểm reframe × measurement bất ngờ × validation thắng baseline (× ICLR: theorem + guarantee). Thiếu một → không Oral.
- *Chấm review tham chiếu:* novelty 8/10 · Oral 7.5–8.5 nếu P3+P5 đủ · feasibility **7/10 ở 12–20 nguồn không V3**.
- **Timing:** vòng 2026 đã đóng (hôm nay 06/2026) → target **2027 cycle** (NeurIPS-ED ~tháng 5/2027 / ICLR ~tháng 9/2026 — xác nhận deadline).

---
# PHẦN X — REFERENCES (đã verify trực tiếp + số liệu chốt)

**Model papers (ICLR Oral):**
- Trust or Escalate — Jung, Brahman, Choi (UW/AI2). arXiv **2407.18370**, ICLR 2025 **Oral**. Selective eval, guarantee P(agree|evaluate)≥1−α qua fixed-sequence testing; Simulated Annotators; Cascaded (Mistral-7B→GPT-4) đạt >80% agreement ~80% coverage.
- Limits to scalable evaluation — ICLR 2025 **Oral** (learning theory), OpenReview **NO6Tv6QcDs**. Judge không hơn model ⇒ không giảm nhãn quá ½; thực tế tệ hơn bound.

**Threat/neighbor đã verify:**
- HAL — arXiv **2510.11977** (ICLR 2026). 9 bench × 9 model, **21,730 rollouts**, ~**$40k**, per-cell accuracy+$+token.
- AI Agents That Matter — arXiv **2407.01502** (TMLR 2024). Cost-controlled eval + Pareto.
- FrugalGPT — arXiv 2305.05176 / TMLR **cSimKw5p6R**. Cascade, **98% cost↓** match best LLM.
- LLMSelector — arXiv **2502.14815**. Per-module selection, **+5–70% acc**, probe động (LLM diagnoser).
- ML.ENERGY — arXiv **2505.06371** (NeurIPS 2025). **40 arch × 6 task**, Joules, **H100/vLLM only**, auto-opt >40%.
- HELM — arXiv 2211.09110. Holistic multi-metric per-model.
- RouterBench — arXiv 2403.12031. **405,467** records × 11 LLM × 8 dataset.

**Extraction feasibility đã verify (gắn C1):**
- AXCELL — `2020.emnlp-main.692`. (task,dataset,metric,value), **F1 25.8** (vs 7.5), semi-auto + LaTeX.
- MOLE — arXiv **2505.19800**. Schema-driven LLM + validation, best **~67.4%** (metadata).
- Computing-Resources in FM — arXiv **2510.13621**. Trích tự động bỏ sót **59.7%/48.3%/88.6%** GPU number/type/hours.
- NLP Reproducibility — `2023.acl-long.568` (ACL 2023). Chỉ **3/24** paper tái lập; accessibility > skill.

**Tầng khác (phân biệt, không cạnh tranh):**
- Circinus — arXiv 2504.16397. SLO-aware **runtime** query planner (KHÁC tầng).
- Cascadia — arXiv 2506.04203 · Routing+Cascading 2410.10347 (tối ưu chọn hệ, không phải evidential decidability).

**Venue:** NeurIPS 2026 ED-track — đặt evaluation làm đối tượng nghiên cứu; mời phân tích failure mode / so sánh assumptions / audit / negative results; "need not outperform". (2026 đã đóng → 2027.)

**Background (brief):** Compound AI Systems (BAIR 2024) · DSPy 2310.03714 · Blueprint Architecture 2406.00584 · MedHELM 2505.23802 · Beyond Accuracy 2511.14136. Tooling: GROBID (grobidOrg/grobid).
