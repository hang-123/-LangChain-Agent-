# Workflow State Model 规范

## 1. 目标
定义 WorkflowState 五层模型下各节点的读写边界，匹配 4 Agent + 6 Tool + 1 Gate 架构。

`workflow_state.py` 提供五层 view（`get_background()`, `get_working_set()`, `get_artifacts()`, `get_control()`, `get_telemetry()`），本规范定义 Tool 层的 state 读写边界。

## 2. 分层结构（保持不变）

```json
{
  "background": {
    "run": {},
    "request": {},
    "candidate": {},
    "job_input": {},
    "policy": {}
  },
  "working_set": {
    "retrieval": {},
    "analysis": {},
    "review": {}
  },
  "artifacts": {
    "job": {},
    "matching": {},
    "resume": {},
    "report": {}
  },
  "control": {},
  "telemetry": {}
}
```

## 3. 节点读写边界

### 3.1 Agent 层

| 节点 | 主要读取 | 主要写入 |
|------|---------|---------|
| **Supervisor** | `background.request.query`, `background.candidate`, `background.job_input`, `background.run.run_manifest`, `background.request.memory_summary` | `background.request.intent`, `background.request.query_profile`, `control.status`, `working_set.analysis.query_result.intent_reason`, `working_set.analysis.query_result.workflow_id` |
| **AnalysisAgent** | `background.request`, `working_set.retrieval.evidence_items`, `artifacts.job`, `artifacts.matching`, `artifacts.resume` | `working_set.analysis.query_result`, `working_set.analysis.insight_result`, `working_set.analysis.quality_metrics` |
| **ReportAgent** | `background`, `working_set.analysis`, `artifacts`, `control`, `working_set.review` | `artifacts.report.report_content`, `working_set.analysis.render_metadata` |

### 3.2 Tool 层

| 节点 | 主要读取 | 主要写入 |
|------|---------|---------|
| **SearchOrchestrator** | `background.request`, `background.policy` | `working_set.retrieval`（全子层）, `working_set.analysis.query_result.search_summary` |
| **JobAnalyzer** | `working_set.retrieval.evidence_items`, `background.request.query_profile`, `background.job_input.raw_jd_text` | `artifacts.job.external_evidence_pack`, `artifacts.job.job_snapshot`, `artifacts.job.archetype_detection`, `artifacts.job.legitimacy_assessment` |
| **MatchingEngine** | `background.candidate`, `artifacts.job.job_snapshot`, `artifacts.job.archetype_detection` | `artifacts.matching.match_assessment` |
| **ResumeTailor** | `background.candidate`, `artifacts.job.job_snapshot`, `artifacts.matching.match_assessment` | `artifacts.resume.tailor_plan`, `artifacts.resume.resume_version`, `artifacts.resume.fact_check_report` |
| **ResumeParser** | `background.job_input`(resume_file) | `background.candidate.candidate_profile`, `background.candidate.resume_evidence` |
| **InterviewCoach** | `background.candidate`, `artifacts.job.job_snapshot`, `artifacts.matching.match_assessment` | `artifacts.interview.prep_pack` |
| **OfferEvaluator** | `background.request.offer_list` | `artifacts.offer.offer_comparison` |
| **ApplicationStore** | `application_store_request`(operation + payload) | `application_store_response`(application_record + previous_status) |

### 3.3 Gate 层

| 节点 | 主要读取 | 主要写入 |
|------|---------|---------|
| **Gate** | `artifacts.*`, `background.policy`, `working_set.retrieval.retrieval_diagnostics` | `control.quality_mode`, `control.warning_message`, `control.root_cause`, `working_set.analysis.quality_metrics` |

## 4. 新增 state 字段

在扁平 `AgentState` 中包含以下字段（已全部实现）：

```python
# career-ops 集成
"archetype_detection": Dict[str, Any]        # 岗位原型检测结果
"adaptive_framing": Dict[str, Any]           # 自适应叙事角度
"legitimacy_assessment": Dict[str, Any]      # 岗位合法性评估
"offer_evaluation": Dict[str, Any]           # offer 对比结果
"gap_analysis": List[Dict[str, Any]]         # 匹配差距分析
"level_strategy": Dict[str, Any]             # 候选人级别策略
"score_interpretation": Dict[str, Any]       # 分数解释

# 记忆系统
"memory_summary": str                        # 历史对话摘要
"memory_artifact_refs": Dict[str, Any]       # 历史 artifact 引用
"working_memory": List[Dict[str, Any]]       # 工作记忆（当前 session 上下文）
"memory_hits": List[Dict[str, Any]]          # 记忆检索命中
	# v2.0 分类型记忆通道（由 MemoryRetrievalNode 注入，供不同 agent 使用）
	"entity_knowledge_memory": Dict[str, Any]    # → SearchAgent query 扩写
	"pattern_memory": Dict[str, Any]             # → Supervisor 路由决策
	"preference_memory": Dict[str, Any]          # → Supervisor + Gate
	"semantic_memory": Dict[str, Any]            # → AnalysisAgent / ReportAgent

# Phase 2 路由与工作流
"workflow_id": str                           # Supervisor 选择的工作流 ID
"missing_artifacts": List[str]               # 缺失的必要输入
"warnings": List[str]                        # Supervisor 警告信息

# Phase 2 Tool 字段
"raw_jd_text": str                           # 原始 JD 文本
"prep_pack": Dict[str, Any]                  # 面试准备包
"verification_report": Dict[str, Any]        # Gate 验证报告
"offer_comparison": Dict[str, Any]           # offer 对比结果
"profile_completeness": float                # 画像完整度
"profile_gaps": List[str]                    # 画像缺口
"resume_file": Dict[str, Any]                # 简历文件信息
"offer_list": List[Dict[str, Any]]           # offer 列表

# Application Store
"application_store_request": Dict[str, Any]  # Supervisor 产出的结构化投递请求
"application_store_response": Dict[str, Any] # ApplicationStore Tool 的响应（含 previous_status）
```

## 5. artifacts 子层扩展

```json
{
  "artifacts": {
    "job": {
      "external_evidence_pack": {},
      "job_snapshot": {},
      "archetype_detection": {},
      "legitimacy_assessment": {}
    },
    "matching": {
      "match_assessment": {},
      "gap_analysis": []
    },
    "resume": {
      "tailor_plan": {},
      "resume_version": {},
      "fact_check_report": {}
    },
    "interview": {
      "prep_pack": {}
    },
    "offer": {
      "offer_comparison": {}
    },
    "report": {
      "report_content": ""
    },
    "application": {
      "application_record": {},
      "previous_status": ""
    }
  }
}
```

## 6. Prompt 注入规则

- Supervisor 的 prompt 注入：`query` + `memory_summary` + `pattern_memory`(v2.0) + `preference_memory`(v2.0) + `candidate_profile`(简要) + `job_input`(简要)
- MemoryRetrievalNode 产出分类型记忆（v2.0）：`entity_knowledge_memory` → SearchAgent query 扩写；`pattern_memory` → Supervisor 路由；`preference_memory` → Gate 过滤；`semantic_memory` → AnalysisAgent/ReportAgent
- AnalysisAgent 的 prompt 注入：所有 `artifacts` 子层 + `working_set.retrieval.evidence_items`，但 `candidate_profile` 只注入摘要
- ReportAgent 的 prompt 注入：`artifacts`（优先）, `control`, `working_set.review`。不注入原始 `evidence_items`
- Tool 层不使用 open-ended prompt，使用结构化 instruction + 输入字段
- Gate 不使用 prompt，纯规则检查

## 7. 迁移策略

### 当前状态（Phase 2 已落地）
- `workflow_state.py` 提供五层 view：`get_background()`, `get_working_set()`, `get_artifacts()`, `get_control()`, `get_telemetry()`
- 底层仍是扁平 `AgentState`，已包含所有 Phase 2 字段（career-ops、记忆系统、路由、Tool、Application Store）
- 节点内部同时存在 `state.get("key")` 和五层 view 两种访问方式，逐步收敛

### 已完成迁移
- Supervisor: 通过 `SupervisorResponse` 结构体写入 `intent` / `workflow_id` / `query_profile` / `application_store_request`
- Gate: 通过 `_gate_node` wrapper 组装五层结构后调用 `run_gate()`，支持 `workflow_id` 参数化
- AnalysisAgent / ReportAgent: 仍使用扁平字段
- Tool 层: 各 Tool 直接读写 `AgentState` 对应字段，符合 Tool 读写边界规范

### 待迁移
- Supervisor: 从 `state.get("query")` 迁移为 `get_background(state)["request"]["query"]`
- AnalysisAgent: 从 `state.get("insights")` 迁移为 `get_working_set(state)["analysis"]`
- ReportAgent: 从 `state.get("report_content")` 迁移为 `get_artifacts(state)["report"]["report_content"]`
- 每次只改一个节点，补对应单测

### 未来计划
- 底层 `AgentState` 从平铺字段迁移为真实分层 schema
- API 层保留兼容输出

## 8. 验收标准
- 每个 Agent/Tool/Gate 在文档中都有明确读写边界
- `CandidateProfile` 与 `ResumeEvidence` 不被下游节点改写
- ReportAgent 与 Gate 优先消费 artifact，而不是重复解析原始证据池
- `context` 不再作为主数据契约
- API 输出包含 `archetype_detection`, `legitimacy_assessment`, `offer_comparison` 等字段
