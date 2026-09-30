# Day 14 — Exercises

## AI Evaluation & Benchmarking · Lab Worksheet

**Thời gian làm bài:** 14:15–17:00

**Domain:** OrbitTech Store Customer Support

Điền trực tiếp câu trả lời vào file này. Golden dataset 20 QA được viết một lần
duy nhất trong `golden_dataset.json`, không chép lại toàn bộ vào Markdown.

---

Từ 14:15–14:30, cài môi trường và chạy baseline tests theo `guide_lab.md`.

---

## Part 1 — Warm-up (14:30–14:45)

### Exercise 1.1 — RAGAS Metric Thresholds

Theo bài giảng:

- 0.8–1.0: Good — monitor, maintain.
- 0.6–0.8: Needs work — analyze failures, iterate.
- Dưới 0.6: Significant issues — investigate.

Với từng metric, xác định khi nào score thấp có thể chấp nhận và khi nào là
critical.

| Metric | Acceptable Low Score Scenario | Critical Low Score Scenario | Action Required |
|---|---|---|---|
| Faithfulness | Câu hỏi ngoài scope hoặc adversarial (vd: xin tư vấn đầu tư, prompt injection đòi lộ system prompt): answer đúng là lời từ chối ngắn + hướng dẫn kênh support, nên ít token trùng với context → score thấp nhưng hành vi đúng. Cũng chấp nhận được khi answer diễn đạt lại (paraphrase) đúng ý mà metric token-overlap không bắt được. | Answer chứa claim không có trong context về những thứ ảnh hưởng trực tiếp tới khách: bịa thông số sản phẩm, thời hạn đổi trả/bảo hành, mức giảm giá, trạng thái đơn hàng, hoặc hứa ngoại lệ/hoàn tiền mà assistant không có quyền. Đây là hallucination → rủi ro pháp lý và mất niềm tin. | Với câu policy/tiền/an toàn: < 0.8 phải phân tích và sửa trước khi release; < 0.6 thì block release. Đọc từng câu sai, xác định claim nào không có evidence; siết system prompt ("chỉ trả lời từ context, nếu không có thì nói không biết"), thêm câu trả lời fallback, giảm temperature, và bổ sung case tương tự vào golden dataset. |
| Answer Relevance | Câu hỏi mơ hồ hoặc gộp nhiều ý, assistant hỏi lại để làm rõ (vd: "đơn nào?", "sản phẩm mua ngày nào?"); hoặc câu adversarial mà assistant chuyển hướng về phạm vi hỗ trợ — không "trả lời thẳng" nhưng là hành vi mong muốn. | Câu hỏi rõ ràng trong scope (vd: "Tai nghe mua online được trả trong bao nhiêu ngày?") nhưng answer lạc đề, trả lời chung chung về chính sách khác, hoặc lặp lại context mà không trả lời câu hỏi. Khách không nhận được thông tin cần thiết. | Kiểm tra query → retrieval có lấy nhầm tài liệu không; nếu retrieval đúng thì sửa prompt để yêu cầu trả lời trực tiếp câu hỏi trước, rồi mới giải thích. Thêm few-shot ví dụ trả lời đúng trọng tâm. |
| Context Recall | Câu out-of-scope/adversarial không có gold evidence trong corpus (expected answer là lời từ chối) nên recall thấp không phản ánh lỗi retriever. Hoặc câu dễ mà chunk đầu tiên đã đủ, phần thiếu chỉ là chi tiết phụ không bắt buộc. | Câu hard/multi-hop cần nhiều tài liệu (vd: đổi trả + bảo hành + policy version theo ngày mua) nhưng retriever bỏ sót tài liệu chứa điều kiện then chốt. Generator không thể trả lời đúng khi thiếu evidence → kéo theo completeness/faithfulness thấp. | Vấn đề nằm ở retrieval: tăng top-k, cải thiện chunking (không cắt ngang điều khoản), thêm hybrid search (BM25 + embedding), query rewriting/tách câu hỏi nhiều ý, bổ sung metadata (doc_id, version) để filter. |
| Context Precision | Recall đã cao và chunk liên quan vẫn nằm trong top-k, chỉ bị xếp sau vài chunk nhiễu; model vẫn trả lời đúng → ảnh hưởng thực tế nhỏ, chỉ tốn thêm token. | Chunk nhiễu xếp đầu và chứa thông tin mâu thuẫn/dễ nhầm (vd: policy phiên bản cũ, chính sách của nhóm sản phẩm khác, điều kiện thành viên khác hạng) khiến generator dùng nhầm → sai câu trả lời. | Thêm reranker (cross-encoder hoặc overlap-based như Exercise 3.5), filter theo metadata/version hiệu lực, giảm top-k sau rerank, xem lại chunk size để mỗi chunk chỉ chứa một chủ đề. |
| Completeness | Expected answer có thêm chi tiết phụ (lời chào, gợi ý kênh liên hệ) mà answer bỏ qua nhưng vẫn đủ ý chính; hoặc answer paraphrase đúng nhưng khác từ ngữ nên token-overlap thấp. Câu adversarial trả lời từ chối ngắn gọn cũng có thể thấp. | Answer thiếu điều kiện hoặc ngoại lệ quan trọng: thiếu phí restocking 10% khi trả máy đã mở hộp hoặc yêu cầu gỡ activation lock trước khi trả, thiếu bước escalation khi nghi bị hack tài khoản, thiếu cảnh báo an toàn với thiết bị pin phồng/quá nhiệt. Thiếu những ý này có thể khiến khách làm sai hoặc gặp nguy hiểm. | Kiểm tra Context Recall trước: nếu thấp → lỗi retrieval; nếu cao → lỗi generation. Sửa prompt yêu cầu liệt kê đủ điều kiện/ngoại lệ/bước tiếp theo, thêm few-shot answer đầy đủ, và bổ sung LLM judge hoặc human review để phân biệt "thiếu ý thật" với "chỉ khác từ ngữ". |

**Nguyên tắc chung:** mức nghiêm trọng phụ thuộc vào loại câu hỏi. Với câu
policy/tiền/an toàn/bảo mật, ngưỡng nên chặt hơn: Faithfulness cần ≥ 0.8,
dưới 0.8 phải sửa trước khi release và dưới 0.6 thì block release; với câu
out-of-scope/adversarial, cần đánh giá hành vi (từ chối đúng, không lộ thông tin)
thay vì chỉ dựa vào điểm token-overlap. Khi debug, đi theo thứ tự pipeline:
Context Recall → Context Precision → Faithfulness → Relevance/Completeness để
xác định lỗi nằm ở retrieval hay generation.

### Exercise 1.2 — Bias trong LLM-as-a-Judge

Ba bias thường gặp:

- Position bias: judge ưu tiên answer xuất hiện trước.
- Verbosity bias: judge ưu tiên answer dài hơn.
- Self-preference: judge ưu tiên output giống chính model đó.

**Câu 1: Thiết kế experiment phát hiện position bias với ít nhất hai conditions.**

> *Câu trả lời:*

**Câu 2: Làm thế nào giảm verbosity bias bằng rubric design?**

> *Câu trả lời:*

**Câu 3: Tại sao cần calibrate LLM judge với human labels?**

> *Câu trả lời:*

### Exercise 1.3 — Evaluation trong CI/CD

**Câu 1: Chọn threshold để block deployment.**

| Metric | Threshold | Lý do |
|---|---:|---|
| Faithfulness | | |
| Answer Relevance | | |
| Completeness | | |

**Câu 2: Khi nào dùng offline evaluation, online evaluation và human review?**

> *Câu trả lời:*

---

## Part 2 — Core Coding (14:45–15:40)

Hoàn thiện các TODO bắt buộc trong `template.py`.

### Task 1 — Data Models

- `QAPair`: question, expected answer, gold context, metadata và retrieved contexts.
- `EvalResult`: answer-side scores, optional retrieval scores, pass/failure fields.
- `overall_score()`: trung bình Faithfulness, Relevance và Completeness.

### Task 2 — RAGASEvaluator

Answer-side:

- `evaluate_faithfulness(answer, context)`
- `evaluate_relevance(answer, question)`
- `evaluate_completeness(answer, expected)`

Retrieval-side:

- `evaluate_context_recall(contexts, expected)`
- `evaluate_context_precision(contexts, expected)`

Full pipeline:

- `run_full_eval(..., contexts=None)` luôn tính ba answer metrics.
- Nếu có `contexts`, tính và lưu thêm Context Recall và Context Precision.
- Retrieval scores không làm thay đổi `overall_score()` và pass rule gốc.

### Task 3 — LLMJudge

- `score_response(question, answer, rubric)`
- `detect_bias(scores_batch)`

### Task 4 — BenchmarkRunner

- `run(qa_pairs, agent_fn, evaluator)`
- `generate_report(results)`
- `run_regression(new_results, baseline_results)`
- `identify_failures(results, threshold)`

`BenchmarkRunner.run()` phải truyền `pair.retrieved_contexts` vào
`run_full_eval()`. Report phải có average của hai retrieval metrics.

### Task 5 — FailureAnalyzer

- `categorize_failures(failures)`
- `find_root_cause(failure)`
- `generate_improvement_suggestions(failures)`
- `generate_improvement_log(failures, suggestions)`

Kiểm tra:

```bash
pytest tests/ -v
```

`rerank_by_overlap()` là TODO bonus của Exercise 3.5. Test tương ứng được skip
nếu bạn chưa làm bonus.

---

## Part 3 — Golden Dataset & Real Benchmark (15:40–16:35)

### Exercise 3.1 — Build the Golden Dataset

Thiết kế và validate dataset theo Mục 5–6 trong `guide_lab.md`. Nội dung 20 QA
được điền trực tiếp trong `golden_dataset.json`; phần dưới chỉ ghi lại kết quả
và quyết định thiết kế, không chép lại toàn bộ QA.

**Kết quả dataset**

| Hạng mục | Kết quả |
|---|---|
| Tổng số records | ____ / 20 |
| Easy | ____ / 5 |
| Medium | ____ / 7 |
| Hard | ____ / 5 |
| Adversarial | ____ / 3 |
| Source documents được sử dụng | ____ / 10 |
| Validator status | PASS / FAIL |

**Ba case đại diện cho quyết định thiết kế**

| ID | Difficulty | Source document(s) | Vì sao case phù hợp với difficulty/attack type? |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

**Điểm khó nhất khi xây dựng expected answer hoặc evidence là gì?**

> *Câu trả lời:*

**Xác nhận:**

- [ ] Mọi claim trong expected answer đều có evidence hỗ trợ.
- [ ] Không có questions trùng ý và không dùng kiến thức ngoài corpus.
- [ ] `python validate_golden_dataset.py` báo `PASS`.

### Exercise 3.2 — Benchmark Run

Chạy:

```bash
python domain_assistant.py
python evaluate_answers.py
```

Copy bảng terminal vào đây hoặc điền từ `artifacts/benchmark_results.json`.

| ID | Question (short) | Ctx Recall | Ctx Precision | Faithfulness | Relevance | Completeness | Overall | Passed? | Failure Type |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| E01 | | | | | | | | | |
| E02 | | | | | | | | | |
| E03 | | | | | | | | | |
| E04 | | | | | | | | | |
| E05 | | | | | | | | | |
| M01 | | | | | | | | | |
| M02 | | | | | | | | | |
| M03 | | | | | | | | | |
| M04 | | | | | | | | | |
| M05 | | | | | | | | | |
| M06 | | | | | | | | | |
| M07 | | | | | | | | | |
| H01 | | | | | | | | | |
| H02 | | | | | | | | | |
| H03 | | | | | | | | | |
| H04 | | | | | | | | | |
| H05 | | | | | | | | | |
| A01 | | | | | | | | | |
| A02 | | | | | | | | | |
| A03 | | | | | | | | | |

**Aggregate Report**

- Overall pass rate: ____%
- Avg Context Recall: ____
- Avg Context Precision: ____
- Avg Faithfulness: ____
- Avg Relevance: ____
- Avg Completeness: ____
- Failure type distribution: ____

**Ba cases có Overall Score thấp nhất**

1. ID: ____ | Score: ____ | Failure type: ____
2. ID: ____ | Score: ____ | Failure type: ____
3. ID: ____ | Score: ____ | Failure type: ____

**Nhận xét ngắn:** Metric nào yếu nhất? Kết quả gợi ý vấn đề nằm ở retrieval
hay generation?

> *Câu trả lời:*

### Exercise 3.3 — LLM-as-a-Judge Rubric Design

Thiết kế rubric domain-specific cho OrbitTech Customer Support. Mỗi mức phải
đủ cụ thể để hai người chấm độc lập có thể hiểu giống nhau.

Chọn 3–5 dimensions:

- [ ] Correctness
- [ ] Completeness
- [ ] Relevance
- [ ] Evidence/citation
- [ ] Actionability
- [ ] Safety/privacy
- [ ] Tone/clarity
- [ ] Dimension khác: __________

| Score | Tiêu chí domain-specific | Ví dụ response |
|---:|---|---|
| 5 | | |
| 4 | | |
| 3 | | |
| 2 | | |
| 1 | | |

**Ba edge cases khó chấm**

| Edge Case | Tại sao khó chấm? | Rubric xử lý thế nào? |
|---|---|---|
| | | |
| | | |
| | | |

**Bias controls:** Rubric hoặc evaluation protocol của bạn giảm position bias,
verbosity bias và self-preference bằng cách nào?

> *Câu trả lời:*

### Exercise 3.4 — Framework Comparison (Bonus +5)

Chỉ làm sau khi hoàn thành 3.1–3.3. Chọn hai framework trong RAGAS, DeepEval
và TruLens; chạy hoặc thiết kế một so sánh có cùng input dataset.

| Tiêu chí | Framework 1: ____ | Framework 2: ____ |
|---|---|---|
| Setup complexity | | |
| Metrics available | | |
| CI/CD integration | | |
| Kết quả trên cùng dataset | | |
| Insight rút ra | | |

- Scores có nhất quán không?
- Framework nào strict hơn và vì sao?
- Hai framework có tìm ra cùng failure cases không?

> *Phân tích:*

### Exercise 3.5 — Retrieval Reranking (Bonus +5)

Mục tiêu: kiểm tra việc đổi thứ tự chunks có tăng Context Precision mà không
thay đổi Context Recall hay không.

1. Chọn ít nhất 5 cases từ `artifacts/actual_answers.json`.
2. Tính Context Recall và Context Precision trước rerank.
3. Implement `rerank_by_overlap()` hoặc một reranker khác.
4. Rerank cùng tập chunks, không thêm hoặc xóa chunk.
5. Tính lại hai metrics và giải thích kết quả.

| ID | Recall before | Recall after | Precision before | Precision after | Delta Precision |
|---|---:|---:|---:|---:|---:|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| **Avg** | | | | | |

**Tại sao Recall dự kiến không đổi?**

> *Câu trả lời:*

**Khi nào reranking không đủ và cần sửa retriever/query/chunking?**

> *Câu trả lời:*

---

## Part 4 — Reflection (16:35–16:50)

Hoàn thành `reflection.md` bằng kết quả thật từ Exercise 3.2.

---

## Completion Checklist

Hoàn thành kiểm tra cuối trong khoảng 16:50–17:00.

- [ ] Tất cả required tests pass.
- [ ] `golden_dataset.json` validate thành công.
- [ ] Exercise 3.1 hoàn thành trong file JSON và bảng kết quả phía trên.
- [ ] Exercise 3.2 có năm metrics, aggregate report và ba cases thấp nhất.
- [ ] Exercise 3.3 có rubric 1–5 và bias controls.
- [ ] `reflection.md` có ba failure analyses và regression strategy.
- [ ] Đã copy `template.py` thành `solution/solution.py`.
- [ ] Exercise 3.4 và 3.5 chỉ làm nếu chọn bonus.
