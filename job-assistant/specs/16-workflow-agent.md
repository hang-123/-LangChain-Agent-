# Workflow Agent 规范（阶段二）

## 1. 目标
WorkflowAgent 在阶段二升级为完整的编排引擎。当 Supervisor 选定工作流后，WorkflowAgent 负责：
- 按工作流定义顺序调用 Agent/Tool/Gate
- 传递 WorkflowState 在各节点间
- 支持从最近成功节点恢复
- 支持按 artifact 粒度只重跑失败节点
- 确保状态写入幂等

## 2. 工作流定义

### 2.1 wf_match_v2
```
SearchOrch → JobAnalyzer → MatchingEngine → AnalysisAgent → ReportAgent → Gate
```

**输入**：query + candidate_profile(可选) + resume_evidence(可选) + job_posting(可选) + raw_jd_text(可选)

**输出**：JobSnapshot + MatchAssessment + 分析报告

**步骤说明**：
1. SearchOrch：根据 query+query_profile 做 Tavily+RAG 并发检索
2. JobAnalyzer：生成 JobSnapshot（如有 raw_jd_text 则先解析），含 ArchetypeDetection + LegitimacyAssessment
3. MatchingEngine：候选人×岗位的关键词匹配
4. AnalysisAgent：深度分析（风险、洞察、行动项）
5. ReportAgent：生成结构化报告 + 自审
6. Gate：质量检查 + 事实边界，通过后交付

### 2.2 wf_resume_tailor_v2
```
JobAnalyzer → MatchingEngine → ResumeTailor → AnalysisAgent → ReportAgent → Gate
```

**输入**：candidate_profile + resume_evidence + job_snapshot(可选) + raw_jd_text(可选)

**输出**：MatchAssessment + ResumeTailoringPlan + ResumeVersion + FactCheckReport

**步骤说明**：
1. JobAnalyzer：生成/复用 JobSnapshot
2. MatchingEngine：匹配分析
3. ResumeTailor：关键词覆盖 + section 改写 + 内置 fact check
4. AnalysisAgent：简历改写策略深度分析
5. ReportAgent：简历改写报告
6. Gate：最终事实校验

### 2.3 wf_interview_prep_v2
```
JobAnalyzer → MatchingEngine → InterviewCoach → AnalysisAgent → ReportAgent → Gate
```

**输入**：candidate_profile + resume_evidence + job_snapshot(可选)

**输出**：MatchAssessment + InterviewPrepPack

### 2.4 wf_profile_bootstrap
```
ResumeParser → Gate (profile_completeness检查)
```

**输入**：简历文件（PDF/DOCX/TXT/Markdown）

**输出**：CandidateProfile + ResumeEvidence + profile_completeness

### 2.5 wf_offer_compare
```
OfferEvaluator → ReportAgent → Gate
```

**输入**：多个 offer 数据列表

**输出**：OfferComparison + 报告

### 2.6 wf_application_followup_v1（阶段三）
```
ApplicationStore(create/update) → Gate
```

## 3. 输入
```json
{
  "workflow_id": "wf_match_v2",
  "user_id": "user_001",
  "workflow_state": {
    "background": {},
    "artifacts": {}
  }
}
```

## 4. 输出
```json
{
  "workflow_status": "completed",
  "completed_steps": ["SearchOrch", "JobAnalyzer", "MatchingEngine", "AnalysisAgent", "ReportAgent", "Gate"],
  "pending_steps": [],
  "artifacts": {},
  "next_recommended_action": "继续生成简历定制建议"
}
```

## 5. 编排原则
- 先事实抽取，再分析，再生成建议
- 任何生成型步骤都依赖前置结构化结果
- Tool 可以跳过（如 MatchingEngine 输入不足时返回保守结果），但 Gate 不可跳过
- 如果某步关键输入缺失，工作流停在可恢复状态
- 工作流状态按 background / working_set / artifacts / control / telemetry 分层
- 每个节点只能写入自己负责的 state 区域

## 6. 恢复策略
- 支持从最近一个成功步骤恢复
- 支持按 artifact 粒度恢复：只重跑失败节点，不重复执行已确认资产
- 每次运行记录输入摘要、版本和时间戳
- Gate rejected → 标注 root_cause 并回退到问题源节点（如 retrieval → SearchOrch, attribution → AnalysisAgent）
- 连续 2 次 rejected → 降级为 conservative 模式，向用户明确说明

## 7. 空状态处理
各 Tool 在输入不足时的行为：
- SearchOrch：正常执行（只要有 query）
- JobAnalyzer：无 evidence_items 时生成保守版 JobSnapshot（仅基于 query_profile 推断）
- MatchingEngine：无 resume_evidence → 返回保守降级分析（overall_score <= 58）
- ResumeTailor：无 candidate_profile → 返回空 artifacts
- InterviewCoach：无 match_assessment → 先生成 wf_match_v2
- OfferEvaluator：offer 数 < 2 → 返回错误

## 8. 禁止事项
- 不得跳过 Gate 进入交付
- 不得在一个工作流里悄悄修改候选人长期画像
- 不得在工作流失败时静默丢弃中间产物

## 9. 实现文件
- `api/core/graph.py` — build_workflow() 函数（替代 build_career_research_graph()）
- `api/core/workflow_state.py` — WorkflowState 读写（已有）
- `api/core/executor.py` — ResearchExecutionSession（已有，需更新工作流入口）

## 10. 与阶段一的差异
| 维度 | 阶段一 | 阶段二 |
|------|--------|--------|
| 工作流数 | 2条（固定线性图） | 6条（Supervisor 按需选择） |
| 编排 | LangGraph 2节点+线性边 | 固定序列调用，无图依赖 |
| 恢复 | ReviewAgent 回退到单个节点 | 按 artifact 粒度恢复 |
| Gate | 无统一 Gate | 每条工作流末尾 Gate |
| Supervisor | 无 | 前置路由 |
