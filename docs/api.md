# Career Research Assistant API

基于 LangGraph + Tavily + SSE 的多 Agent 求职研究助手 API。

- **Base URL**: `http://localhost:9000`
- **Version**: 2.1.0
- **Content-Type**: `application/json`
- **Streaming**: `text/event-stream` (SSE)

---

## 目录

- [架构概览](#架构概览)
- [Health](#health)
- [Metrics](#metrics)
- [Research](#research)
  - [POST /api/research/run](#post-apiresearchrun)
  - [GET /api/research/stream](#get-apiresearchstream)
  - [POST /api/research/stream](#post-apiresearchstream)
- [Evaluation](#evaluation)
  - [GET /api/research/cases](#get-apiresearchcases)
  - [POST /api/research/cases/run](#post-apiresearchcasesrun)
  - [POST /api/research/eval](#post-apiresearcheval)
- [数据模型](#数据模型)
  - [请求模型](#请求模型)
  - [响应模型](#响应模型)
  - [Agent Pipeline 内部结构](#agent-pipeline-内部结构)
- [错误码](#错误码)

---

## 架构概览

```
Client
  │
  ├── POST /api/research/run      ──▶  同步执行 7-agent LangGraph pipeline
  ├── GET  /api/research/stream   ──▶  SSE 流式执行，实时推送每个节点状态
  └── POST /api/research/stream   ──▶  同上（支持完整 payload）
              │
              ▼
┌──────────────────────────────────────────────────────┐
│  LangGraph State Machine (7 nodes)                   │
│                                                      │
│  IntentRouterNode ──▶ SearchAgent ──▶ QueryAgent     │
│                                          │            │
│                                          ▼            │
│                                     InsightAgent     │
│                                          │            │
│                                          ▼            │
│                                     QualityGate      │
│                                          │            │
│                                          ▼            │
│                     ReviewAgent ◀── ReportAgent       │
│                       │                              │
│                       ▼ (retry loop, max 3)          │
│              QueryAgent / InsightAgent / ReportAgent  │
└──────────────────────────────────────────────────────┘
```

**节点说明**:

| 节点 | 职责 |
|------|------|
| IntentRouterNode | 意图识别：`general` / `tech_coding` / `salary_culture` |
| SearchAgent | 并发检索 6 个工具源（公司画像、JD、面经、技术栈、薪资文化、Tavily） |
| QueryAgent | 证据归因、公司差异分析、生成结构化 claims |
| InsightAgent | 风险诊断、面试官追问设计、一周行动项生成 |
| QualityGate | 成稿前质量闸门判定 |
| ReportAgent | 流式 Markdown 报告生成 |
| ReviewAgent | 质量审查 + 回退路由（最多 3 次重试、熔断保护） |

---

## Health

### `GET /api/health`

健康检查。

**Response** `200 OK`

```json
{
  "status": "ok",
  "service": "career-research-assistant"
}
```

**curl**

```bash
curl http://localhost:9000/api/health
```

---

## Metrics

### `GET /metrics`

Prometheus 指标端点（需启用 `PROMETHEUS_ENABLED=true`）。

**Response** `200 OK` — Prometheus text format.

**Error** `404` — metrics 未启用或 `prometheus_client` 不可用。

```bash
curl http://localhost:9000/metrics
```

---

## Research

### `POST /api/research/run`

同步执行一次完整的研究 pipeline，返回最终结果。

**Request** `application/json`

```json
{
  "query": "帮我研究字节跳动后端开发实习",
  "candidate_profile": {},
  "resume_evidence": [],
  "job_posting": {},
  "match_assessment": {}
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `query` | string | **yes** | 2–600 chars | 研究查询，格式：公司 + 岗位 + 研究目标 |
| `candidate_profile` | object | no | — | 候选人画像（简历定制模式时必填） |
| `resume_evidence` | object[] | no | 每项需含 `evidence_id` + `section`/`evidence_type` | 简历证据列表（与 `candidate_profile` 同时提供） |
| `job_posting` | object | no | — | 外部传入的职位描述 |
| `match_assessment` | object | no | — | 外部传入的匹配评估 |

**Validation**: 如果提供 `candidate_profile`，则必须同时提供 `resume_evidence`，且 `candidate_profile.candidate_id` 不可为空。

**Response** `200 OK`

```json
{
  "run_id": "run_20260506_abc123",
  "report_markdown": "## 字节跳动 后端开发实习 深度研究报告\n\n...",
  "insights": {
    "company": "字节跳动",
    "role": "后端开发实习",
    "intent": "general",
    "company_signals": ["..."],
    "company_specific_requirements": ["..."],
    "technical_stack_requirements": ["Go", "Python", "Kafka", "..."],
    "candidate_risks": ["..."],
    "interviewer_questions": ["..."],
    "action_plan_items": [
      {
        "day": 1,
        "priority": "high",
        "goal": "建立公司差异画像",
        "task": "...",
        "why_this_company": "...",
        "expected_outcome": "...",
        "evidence_refs": ["..."]
      }
    ]
  },
  "tailor_plan": {},
  "resume_version": {},
  "fact_check_report": {},
  "external_evidence_pack": {},
  "job_snapshot": {},
  "match_assessment": {},
  "run_manifest": {
    "run_id": "run_20260506_abc123",
    "query": "帮我研究字节跳动后端开发实习",
    "prompt_version": "v2",
    "policy_version": "v2",
    "experiment_id": "",
    "variant": "control"
  },
  "review": {
    "passed": true,
    "quality_score": 85,
    "issues": [],
    "retry_target": "report",
    "root_cause": "synthesis"
  },
  "retry_count": 0,
  "quality_summary": {
    "quality_mode": "normal",
    "evidence_count": 8,
    "company_specific_source_count": 4,
    "claim_evidence_coverage": 82
  },
  "trace": [],
  "quality_mode": "normal",
  "warning_message": "",
  "root_cause": "",
  "workflow_state": {
    "background": {},
    "working_set": {},
    "artifacts": {},
    "control": {},
    "telemetry": {}
  }
}
```

**Errors**

| Status | detail | 说明 |
|--------|--------|------|
| 400 | `query must not be empty` | query 为空 |
| 400 | `query blocked by guardrails: detected prompt exfiltration pattern` | 输入命中注入规则 |
| 400 | `candidate_profile and resume_evidence must be provided together` | 简历定制参数不完整 |
| 400 | `candidate_profile must include candidate_id` | 缺少 candidate_id |
| 500 | `LangGraph failed: ...` | pipeline 执行异常 |

**curl**

```bash
curl -X POST http://localhost:9000/api/research/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "帮我研究字节跳动后端开发实习，重点看真实JD、面经和一周准备动作。"
  }'
```

带简历定制参数:

```bash
curl -X POST http://localhost:9000/api/research/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "帮我研究美团后端开发",
    "candidate_profile": {
      "candidate_id": "cand_001",
      "name": "张三",
      "current_role": "后端开发"
    },
    "resume_evidence": [
      {
        "evidence_id": "ev_001",
        "section": "work_experience",
        "content": "负责广告投放系统后端开发..."
      }
    ]
  }'
```

---

### `GET /api/research/stream`

SSE 流式执行研究 pipeline，实时推送每个 Agent 节点的状态、token 级报告内容、以及最终结果。

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **yes** | 研究查询 (min 2 chars) |

**Response** `200 OK` — `text/event-stream`

SSE 事件类型:

| `type` | 触发时机 | 关键字段 |
|--------|----------|----------|
| `meta` | 会话开始 | `run_id`, `query`, `max_retries`, `run_manifest` |
| `status` | 每个节点开始/完成 | `node`, `agent`, `phase` (`started`/`completed`), `detail`, `retry_count` |
| `chunk` | ReportAgent 流式输出 | `content` (Markdown token) |
| `message` | 每个节点完成 | `speaker`, `content`, `metadata` (节点特定结构化摘要) |
| `done` | 全部完成 | `report_markdown`, `insights`, `tailor_plan`, `quality_summary`, `workflow_state` |
| `error` | 异常中断 | `error_type`, `detail`, `traceback` |

**`message` 事件的 `speaker` 枚举**:

| speaker | content 摘要 |
|---------|-------------|
| `IntentRouterNode` | 已完成意图识别与确定性分流 |
| `SearchAgent` | 已完成并发检索 |
| `QueryAgent` | 已输出岗位要求、技术栈、薪资线索和面试官期待 |
| `InsightAgent` | 已输出风险点、面试官追问和准备策略 |
| `QualityGate` | 已完成成稿前质量闸门判定 |
| `ReportAgent` | 已完成本轮流式成稿 |
| `ReviewAgent` | 已完成本轮审查 |

**示例 SSE 流**:

```
data: {"type":"meta","run_id":"run_xxx","query":"...","max_retries":3,...}

data: {"type":"status","run_id":"run_xxx","node":"IntentRouterNode","agent":"IntentRouterNode","phase":"started","detail":"正在识别意图并分流","retry_count":0,...}

data: {"type":"status","run_id":"run_xxx","node":"IntentRouterNode","agent":"IntentRouterNode","phase":"completed","detail":"IntentRouterNode 已完成意图识别","retry_count":0,...}

data: {"type":"message","run_id":"run_xxx","speaker":"IntentRouterNode","content":"IntentRouterNode 已完成意图识别与确定性分流。","metadata":{"intent":"general","company":"字节跳动","role":"后端开发实习"},...}

data: {"type":"status","run_id":"run_xxx","node":"SearchAgent","agent":"SearchAgent","phase":"started","detail":"正在执行多源并发检索","retry_count":0,...}

...

data: {"type":"chunk","run_id":"run_xxx","node":"ReportAgent","content":"## 字节跳动"},...

data: {"type":"chunk","run_id":"run_xxx","node":"ReportAgent","content":" 后端开发实习"},...

...

data: {"type":"done","run_id":"run_xxx","node":"System","report_markdown":"...","retry_count":0,...}
```

**curl**

```bash
curl -N "http://localhost:9000/api/research/stream?query=帮我研究字节跳动后端开发实习"
```

**前端 EventSource 示例**:

```javascript
const es = new EventSource(
  `http://localhost:9000/api/research/stream?query=${encodeURIComponent('帮我研究字节跳动后端开发实习')}`
);

es.addEventListener('message', (e) => {
  const event = JSON.parse(e.data);
  switch (event.type) {
    case 'meta':
      console.log('Run started:', event.run_id);
      break;
    case 'chunk':
      // 追加 Markdown token
      reportEl.textContent += event.content;
      break;
    case 'done':
      console.log('Completed:', event.report_markdown);
      es.close();
      break;
    case 'error':
      console.error(event.detail);
      es.close();
      break;
  }
});
```

---

### `POST /api/research/stream`

与 `GET /api/research/stream` 相同，但支持完整 Request Body（同 [`POST /api/research/run`](#post-apiresearchrun)），可附带 `candidate_profile`、`resume_evidence` 等字段。

**Request** 同 `ResearchRunRequest`。

**Response** 同 `GET /api/research/stream` SSE 流。

```bash
curl -N -X POST http://localhost:9000/api/research/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "帮我研究腾讯后台开发岗位",
    "candidate_profile": {"candidate_id": "cand_001"}
  }'
```

---

## Evaluation

### `GET /api/research/cases`

获取所有预置评测用例。

**Response** `200 OK`

```json
[
  {
    "case_id": "general_bytedance_backend_intern",
    "query": "帮我研究字节跳动后端开发实习，重点看真实JD、面经和一周准备动作。",
    "expected_intent": "general",
    "minimum_evidence_count": 4,
    "company_assertions": ["字节", "后端"],
    "allow_conservative": true,
    "risk_tags": ["company_specificity", "interview_expectations"]
  },
  {
    "case_id": "tech_meituan_backend",
    "query": "帮我研究美团后端开发，重点看技术栈、系统设计、算法和真实面经。",
    "expected_intent": "tech_coding",
    "minimum_evidence_count": 4,
    "company_assertions": ["美团", "技术栈"],
    "allow_conservative": true,
    "risk_tags": ["technical_stack", "coding_depth"]
  },
  {
    "case_id": "culture_tencent_backend",
    "query": "帮我研究腾讯后台开发岗位，重点看薪资区间、团队文化、工作节奏和匹配风险。",
    "expected_intent": "salary_culture",
    "minimum_evidence_count": 4,
    "company_assertions": ["腾讯", "文化"],
    "allow_conservative": true,
    "risk_tags": ["salary_signal", "culture_fit"]
  }
]
```

```bash
curl http://localhost:9000/api/research/cases
```

---

### `POST /api/research/cases/run`

按 `case_id` 执行单个评测用例。

**Request**

```json
{
  "case_id": "general_bytedance_backend_intern"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `case_id` | string | **yes** | 预置用例 ID (min 3 chars) |

**Response** `200 OK` — 同 `ResearchRunResponse`。

**Error** `404` — `unknown case_id: <case_id>`。

```bash
curl -X POST http://localhost:9000/api/research/cases/run \
  -H "Content-Type: application/json" \
  -d '{"case_id": "general_bytedance_backend_intern"}'
```

---

### `POST /api/research/eval`

批量执行评测用例并汇总结果。

**Request**

```json
{
  "case_ids": ["general_bytedance_backend_intern", "tech_meituan_backend"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `case_ids` | string[] | no | 指定要执行的用例 ID 列表。为空则执行全部用例。 |

**Response** `200 OK`

```json
{
  "suite_name": "default",
  "total_cases": 2,
  "passed_cases": 2,
  "failed_cases": 0,
  "average_score": 87.5,
  "root_cause_breakdown": {
    "retrieval": 1,
    "synthesis": 0
  },
  "case_results": [
    {
      "case_id": "general_bytedance_backend_intern",
      "passed": true,
      "score": 85,
      "expected_intent": "general",
      "actual_intent": "general",
      "failures": [],
      "root_cause": "",
      "quality_mode": "normal",
      "metrics": {
        "evidence_count": 8,
        "company_specific_source_count": 4,
        "claim_evidence_coverage": 82,
        "action_plan_source_coverage": 75
      },
      "node_scores": {
        "retrieval": 90,
        "attribution": 85,
        "insight": 80,
        "report_compliance": 85
      },
      "metadata": {
        "run_id": "run_xxx",
        "case_id": "general_bytedance_backend_intern",
        "prompt_version": "v2",
        "policy_version": "v2",
        "model_name": "qwen-plus",
        "experiment_id": "",
        "variant": "control"
      }
    }
  ]
}
```

**Eval Scoring 逻辑**:

| 维度 | 满分 | 扣分项 |
|------|------|--------|
| `retrieval` | 100 | 证据数量不足 (-30), 公司特异性证据不足 (-20), 缺少证据类别 (每类 -10) |
| `attribution` | 100 | claim 覆盖率低 (-35), action plan 覆盖率低 (-25) |
| `insight` | 100 | 缺少风险点 (-20), 缺少追问 (-20), 缺少行动项 (-20), 证据缺口过多 (-10) |
| `report_compliance` | 100 | 缺少必选章节 (-10), 引用 URL 不足 (-20), 缺少公司断言 (-15) |

**Error** `400` — `no cases selected`。

```bash
# 执行全部用例
curl -X POST http://localhost:9000/api/research/eval \
  -H "Content-Type: application/json" \
  -d '{}'

# 执行指定用例
curl -X POST http://localhost:9000/api/research/eval \
  -H "Content-Type: application/json" \
  -d '{"case_ids": ["general_bytedance_backend_intern"]}'
```

---

## 数据模型

### 请求模型

#### `ResearchRunRequest`

```python
class ResearchRunRequest(BaseModel):
    query: str                                  # 2-600 chars
    candidate_profile: dict[str, Any]           # 可选
    resume_evidence: list[dict[str, Any]]       # 可选（与 candidate_profile 同时提供）
    job_posting: dict[str, Any]                 # 可选
    match_assessment: dict[str, Any]            # 可选
```

#### `ResearchCaseRunRequest`

```python
class ResearchCaseRunRequest(BaseModel):
    case_id: str                                # min 3 chars
```

#### `EvalRunRequest`

```python
class EvalRunRequest(BaseModel):
    case_ids: list[str]                         # 空列表 = 全部用例
```

---

### 响应模型

#### `ResearchRunResponse`

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | string | 本次运行的唯一 ID |
| `report_markdown` | string | 最终 Markdown 报告 |
| `insights` | object | 所有 Agent 的聚合分析结果 |
| `tailor_plan` | object | 简历定制计划 |
| `resume_version` | object | 岗位定制版简历 |
| `fact_check_report` | object | 事实校验报告 |
| `external_evidence_pack` | object | 外部证据包 |
| `job_snapshot` | object | 岗位快照 |
| `match_assessment` | object | 人岗匹配评估 |
| `run_manifest` | object | 运行元数据（版本、实验分组等） |
| `review` | object \| null | ReviewAgent 的结构化审查结果 |
| `retry_count` | int | 重试次数 |
| `quality_summary` | object | 质量闸门汇总 |
| `trace` | object[] | 运行 trace |
| `quality_mode` | string | `normal` / `conservative` / `fallback` |
| `warning_message` | string | 质量警告信息 |
| `root_cause` | string | 根因分类 |
| `workflow_state` | object | 完整工作流状态快照（5 个视图） |

#### `workflow_state` 结构

```json
{
  "background": {
    "run": { "run_id": "...", "research_case": {}, "run_manifest": {} },
    "request": { "query": "...", "intent": "...", "query_profile": {} },
    "candidate": { "candidate_profile": {}, "resume_evidence": [] },
    "job_input": { "job_posting": {}, "raw_jd_text": "", "source_url": "" },
    "policy": {}
  },
  "working_set": {
    "retrieval": { "query_pack": [], "evidence_items": [], "context": [], "retrieval_diagnostics": {} },
    "analysis": { "query_result": {}, "insight_result": {}, "quality_metrics": {} },
    "review": { "review_feedback": "" }
  },
  "artifacts": {
    "job": { "external_evidence_pack": {}, "job_snapshot": {} },
    "matching": { "match_assessment": {} },
    "resume": { "tailor_plan": {}, "resume_version": {}, "fact_check_report": {} },
    "report": { "report_content": "" }
  },
  "control": {
    "retry_count": 0,
    "quality_mode": "normal",
    "warning_message": "",
    "root_cause": "",
    "root_cause_history": [],
    "status": ""
  },
  "telemetry": {
    "run_trace": [],
    "quality_summary": {},
    "perf_bill": {},
    "perf_bill_path": "",
    "security_events": []
  }
}
```

#### `EvalSuiteSummary`

| Field | Type | Description |
|-------|------|-------------|
| `suite_name` | string | 评测套件名称 |
| `total_cases` | int | 总用例数 |
| `passed_cases` | int | 通过数 |
| `failed_cases` | int | 失败数 |
| `average_score` | float | 平均分 |
| `root_cause_breakdown` | object | 根因分布 `{"retrieval": N, "attribution": N, ...}` |
| `case_results` | CaseEvaluation[] | 每个用例的详细结果 |

---

### Agent Pipeline 内部结构

#### `QueryProfile` — 意图路由结果

```json
{
  "company": "字节跳动",
  "role": "后端开发实习",
  "team_hint": "推荐后端",
  "job_level": "实习",
  "domain_hint": "推荐",
  "priority_topics": ["Go", "分布式", "高并发"]
}
```

#### `Claim` — QueryAgent 归因结果

```json
{
  "claim_id": "company_specific_requirement-1",
  "claim_type": "company_specific_requirement",
  "statement": "字节跳动后端实习更看重对推荐系统业务场景的理解",
  "evidence_refs": ["[jd] 后端开发实习生 | https://zhaopin.bytedance.com/..."],
  "confidence": 72,
  "company_specific": true
}
```

#### `ActionPlanItem` — InsightAgent 行动项

```json
{
  "day": 1,
  "priority": "high",
  "goal": "建立公司差异画像",
  "task": "把公司画像、JD 和面经里反复出现的业务线索整理成一页差异卡。",
  "why_this_company": "当前 claims 显示字节的岗位重点靠近推荐系统，不先抽象出差异画像会滑回通用模板。",
  "expected_outcome": "一页岗位差异卡，包含业务场景、关键职责、核心约束。",
  "evidence_refs": ["[company_profile] 字节跳动技术团队 | https://..."],
  "priority": "high"
}
```

#### `ReviewAgentResponse` — 审查结果

```json
{
  "passed": false,
  "quality_score": 62,
  "issues": ["claim 证据绑定覆盖率仅 58%，低于阈值 70%"],
  "issue_details": [
    {
      "issue_code": "LOW_CLAIM_COVERAGE",
      "severity": "high",
      "retry_target": "query",
      "root_cause": "attribution",
      "message": "claim_evidence_coverage=58 低于 70，需要 QueryAgent 重新归因"
    }
  ],
  "feedback_markdown": "请 QueryAgent 重点补充以下证据绑定：...",
  "retry_target": "query",
  "root_cause": "attribution"
}
```

---

## 错误码

| HTTP Status | error_type | 说明 |
|-------------|------------|------|
| 400 | `validation_error` | 请求参数校验失败（query 为空、参数不完整、被 guardrails 拦截） |
| 404 | — | 资源不存在（case_id 未找到、metrics 未启用） |
| 500 | `runtime_error` | LangGraph pipeline 执行异常、LLM 调用失败、检索工具异常 |

**SSE 错误事件格式**:

```json
{
  "type": "error",
  "run_id": "run_xxx",
  "node": "System",
  "timestamp": "2026-05-06T12:00:00.000Z",
  "error_type": "runtime_error",
  "detail": "LangGraph执行失败: ...",
  "traceback": "..."
}
```

---

## 环境变量

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `dashscope_compatible` | LLM 提供商 |
| `OPENAI_API_KEY` | — | API Key（兼容 `DASHSCOPE_API_KEY`） |
| `OPENAI_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | LLM Base URL |
| `OPENAI_MODEL` | `qwen-plus` | 模型名称 |
| `TAVILY_API_KEY` | — | Tavily 搜索 API Key |
| `REDIS_URL` | — | Redis 连接 URL |
| `MAX_RETRIES` | `3` | ReviewAgent 最大重试次数 |
| `TAVILY_MAX_RESULTS` | `5` | Tavily 单次最大结果数 |
| `ENABLE_NODE_PERF` | `false` | 启用节点性能追踪 |
| `ENABLE_CACHE` | `false` | 启用检索结果缓存 |
| `CACHE_DB_PATH` | `var/cache/langgraph_cache.sqlite` | SQLite 缓存路径 |
| `ENABLE_RAG` | `false` | 启用 pgvector RAG |
| `RAG_DATABASE_URL` | — | pgvector 数据库 URL |
| `ENABLE_CONVERSATION_MEMORY` | `false` | 启用对话记忆 |
| `ENABLE_OTEL` | `false` | 启用 OpenTelemetry |
| `PROMETHEUS_ENABLED` | `false` | 启用 Prometheus 指标 |
| `ENABLE_GUARDRAILS` | `false` | 启用安全护栏 |
| `GUARDRAILS_MODE` | `minimal_blocking` | 护栏模式 |
| `ENABLE_QUERY_STORE` | `false` | 启用 SQLite 运行持久化 |
| `DEPLOYMENT_ENV` | `local` | 部署环境标识 |

服务器启动: `uvicorn api.main:app --host 0.0.0.0 --port 9000 --reload`
