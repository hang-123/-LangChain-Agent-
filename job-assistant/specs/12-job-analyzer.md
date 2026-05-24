# JobAnalyzer Tool 规范

## 1. 目标
JobAnalyzer 是岗位分析的统一 Tool。

根据输入类型自动选择路径：
- 有 `raw_jd_text` → 先解析 JD 文本 → 再用外部证据增强
- 只有 query/evidence_items → 从检索证据推断 → 标注"未基于真实 JD"
- 始终运行 LegitimacyScorer → 评估岗位合法性

## 2. 职责
- 解析原始 JD，生成 `JobPosting` 与 `JobRequirement`（如有 raw_jd_text）
- 消费 SearchOrchestrator 输出的 evidence_items 生成 `ExternalEvidencePack`
- 输出 `JobSnapshot`（统一的岗位快照）
- 输出 `ArchetypeDetection`（岗位原型分类）
- 输出 `LegitimacyAssessment`（岗位合法性评估）
- 标注证据时效、覆盖度与歧义风险

## 3. 输入
```json
{
  "query_profile": {},
  "evidence_items": [],
  "raw_jd_text": "string (可选)",
  "source_url": "optional",
  "target_company": "optional",
  "target_role": "optional"
}
```

## 4. 输出
```json
{
  "job_snapshot": {
    "job_posting": {},
    "job_requirements": [],
    "external_evidence_pack_id": "jep_xxx",
    "evidence_quality": {}
  },
  "external_evidence_pack": {},
  "archetype_detection": {},
  "legitimacy_assessment": {},
  "risks": ["JD 没写清楚团队方向，领域判断置信度有限"]
}
```

## 5. 执行流程

### Step 1: JD 解析（如有 raw_jd_text）
- LLM 单次调用：提取 company_name, job_title, requirements, salary_range, location
- 每条 requirement 标注 requirement_level（must_have / nice_to_have / bonus）
- 保留原始 evidence_text
- 如果 raw_jd_text 为空 → 跳过

### Step 2: 外部证据增强
- 消费 evidence_items（SearchOrchestrator 输出）
- 合并为 ExternalEvidencePack：保留来源 URL、snippet、置信度
- 提取 company_signals、interview_signals、risk_flags

### Step 3: 岗位快照生成
- 聚合 JobPosting + JobRequirements + ExternalEvidencePack → JobSnapshot
- 计算 evidence_quality（freshness, coverage, ambiguity_notes）
- 标注证据来源路径（真实 JD / 推断）

### Step 4: 原型检测 (ArchetypeDetector)
- 先确定性关键词匹配（ARCHETYPE_KEYWORDS）
- 若 confidence < 0.7：LLM 确认
- 输出 ArchetypeDetection

### Step 5: 合法性评分 (LegitimacyScorer)
- 检查信号：posting_age, tech_specificity, requirements_realism, layoff_signals, repost_count
- 确定性评分（0 LLM）
- 输出 LegitimacyAssessment（tier + signals_table + context_notes）

## 6. 核心规则
- 出现"熟悉/掌握/精通/有经验"时 → 判断为要求项
- 出现"优先/加分"时 → nice_to_have
- 出现薪资、地点、工作制时 → 写入 JobPosting，不混到技能要求
- 外部证据只能增强岗位理解，不能覆盖掉用户明确提供的 JD 事实
- RAG 命中的 evidence_items 与实时检索证据同级处理
- legitimacy_assessment.tier = Suspicious 时 → 在 JobSnapshot 中附带醒目的风险标记

## 7. 非职责
- 不做候选人匹配（MatchingEngine 负责）
- 不做简历改写（ResumeTailor 负责）
- 不做搜索编排（SearchOrchestrator 负责）

## 8. 输出质量要求
- 每条 JobRequirement 必须包含 description 和原始 evidence_text
- ExternalEvidencePack 中的来源必须保留时效或置信度信息
- JobSnapshot 必须保留 evidence_quality 和 ambiguity_notes
- LegitimacyAssessment 的 batch_mode 必须明确标注（Playwright 可用性）
- ArchetypeDetection.confidence < 0.5 时标注"不确定"

## 9. 配置
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ENABLE_LEGITIMACY_SCORER` | `1` | 是否启用合法性评分 |
| `ENABLE_ARCHETYPE_DETECTOR` | `1` | 是否启用原型检测 |

## 10. 实现文件
- `api/tools/job_analyzer.py` — JobAnalyzer 主逻辑
- `api/agents/archetype_detector.py` — 原型检测（被 JobAnalyzer 调用的子模块）
- `api/agents/legitimacy_scorer.py` — 合法性评分（被 JobAnalyzer 调用的子模块）
