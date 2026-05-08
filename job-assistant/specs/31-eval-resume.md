# Eval: Resume 规范

## 1. 目标
评估简历定制输出是否贴岗、真实、可用。

## 2. 评测维度
- `fact_faithfulness`: 是否严格基于原始简历事实
- `job_relevance`: 是否强化了目标岗位最相关信息
- `keyword_coverage`: 是否覆盖关键 JD 关键词
- `readability`: 语言是否清晰、简洁、适合简历场景

## 3. 通过门槛
- `fact_faithfulness = 100%`，任何虚构直接失败
- `job_relevance >= 0.80`
- `keyword_coverage >= 0.70`

## 4. 失败分级
- P0: 虚构项目、角色、指标
- P1: 把弱相关经历错误包装为强相关
- P2: 关键词覆盖不足
- P3: 文风冗长、不像简历

## 5. 人工检查清单
- 是否出现原简历没有的技术名词
- 是否出现原简历没有的数字成果
- 是否能一眼看出与目标岗位的相关性提升

## 6. 实现状态（2026-05-07）

**已实现**:
- `api/evals/harness.py` — `_score_resume()` 函数，覆盖 4 个评分维度：
  - `fact_faithfulness`: fact_check_report.status + forbidden_phrases 检测（P0：任何虚构 → 总分 0）
  - `job_relevance`: section_actions 数量 vs min_section_actions
  - `keyword_coverage`: covered 关键词数量 vs min_keyword_covered + require_keywords 命中率
  - `readability`: section_actions 存在且合理
- `api/core/contracts.py` — `ResearchCase` 新增 `resume_ground_truth` 字段；`NodeScorecard` 新增 `resume` 字段
- `api/core/policies.py` — `EvalPolicy` 新增 `min_resume_score` 阈值（默认 70，高于其他维度以体现 spec 中 fact_faithfulness 的硬要求）
- `api/evals/research_cases.json` — 新增 `resume_tailor_factual` eval case
- `tests/test_resume_scorer.py` — 7 个单元测试（pass, fabrication-zero, rejected-zero, missing-keywords, no-ground-truth, downgraded-partial, full-integration）
- `api/main.py` — `run_research_case` 端点传递 `candidate_profile` 和 `resume_evidence` 给 session

**待实现（Phase 2/后续）**:
- 大规模人工标注样本
- `readability` 维度目前通过 structure 指标间接评估，未引入 NLP 文本可读性指标
