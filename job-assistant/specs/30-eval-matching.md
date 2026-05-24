# Eval: Matching 规范

## 1. 目标
评估岗位匹配分析是否正确、稳定、可解释。

## 2. 数据集要求
- 每条样本包含：简历、JD、人工标注匹配结论。
- 人工标注至少包含：整体建议、3 个优势、3 个差距。
- 至少覆盖校招、实习、社招初级岗位。

## 3. 评测维度
- `score_alignment`: 模型分数与人工区间的一致性
- `must_have_recall`: 对关键硬要求缺口的识别率
- `evidence_precision`: 优势/差距引用证据的准确率
- `recommendation_accuracy`: 建议投递结论准确率

## 4. 通过门槛
- `recommendation_accuracy >= 0.75`
- `must_have_recall >= 0.80`
- `evidence_precision >= 0.85`

## 5. 失败分级
- P0: 把明显不匹配判断成强匹配
- P1: 漏掉关键 `must_have` 差距
- P2: 解释合理但引用证据不准
- P3: 分数波动偏大但建议结论不变

## 6. 样例关注点
- 关键词命中但实际经验很浅
- 项目经历强，但业务域不匹配
- 地点/工作方式约束冲突

## 7. 实现状态（2026-05-07）

**已实现**:
- `api/evals/harness.py` — `_score_matching()` 函数，覆盖 4 个评分维度：
  - `score_alignment`: overall_score vs ground_truth min_overall_score
  - `must_have_recall`: strengths 比例 vs min_must_have_match_ratio
  - `evidence_precision`: strengths 数量 vs min_strengths, gaps 数量 vs max_gaps
  - `recommendation_accuracy`: 建议结论匹配（P0 级失败扣 35 分）
- `api/core/contracts.py` — `ResearchCase` 新增 `candidate_profile`, `resume_evidence`, `match_ground_truth` 字段；`NodeScorecard` 新增 `matching` 字段
- `api/core/policies.py` — `EvalPolicy` 新增 `min_matching_score` 阈值（默认 65）
- `api/evals/research_cases.json` — 新增 3 个 matching eval cases（`match_strong_fit`, `match_skill_gap`, `match_missing_must_have`）
- `tests/test_matching_scorer.py` — 6 个单元测试（pass, penalty, missing, no-ground-truth, partial, full-integration）
- `api/main.py` — `run_research_case` 端点传递 `candidate_profile` 和 `resume_evidence` 给 session

**待实现**:
- 大规模人工标注样本（当前为小型构造样本）
- 与 CI/CD pipeline 集成自动运行
