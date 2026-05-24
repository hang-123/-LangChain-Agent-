# 系统测试规范

## 1. 概述

本规范定义 Job Assistant 的完整测试需求，覆盖 3 Agent + 7 Tool + 1 Gate + 6 Workflow 的分层架构。

### 1.1 测试金字塔

```
                    ┌──────┐
                    │ E2E  │  3-5 条: 完整工作流 + Gate
                    └──────┘
                  ┌──────────┐
                  │ 集成测试  │  10-15 条: workflow 链路集成
                  └──────────┘
              ┌──────────────────┐
              │   Agent 行为测试  │  15-20 条: LLM输出质量
              └──────────────────┘
          ┌──────────────────────────┐
          │    Tool 单元测试          │  25-35 条: 确定性逻辑
          └──────────────────────────┘
      ┌──────────────────────────────────┐
      │     Gate 规则测试                 │  15-25 条: 每规则≥1条
      └──────────────────────────────────┘
```

**策略原则**：
- Tool 和 Gate（确定性逻辑）：高覆盖率，TDD 先行，mock 所有外部依赖
- Agent（LLM 行为）：不追求逐字一致性，用结构化断言（schema 符合性 + 关键字段非空 + 无 forbidden_phrases）
- 集成工作流：只测核心链路，用 fixture 组装
- CI 用 mock LLM，本地手动跑真实 LLM 验证

---

## 2. 测试目标

1. **正确性验证**：每个工作流在给定标准输入时产生符合领域模型定义的输出
2. **边界保护**：Gate 能拦截所有已知类型的虚构/越界输出（拦截率 100%）
3. **Agent 行为一致性**：Agent 在相同输入下行为可复现（结构化输出 schema 符合性 ≥ 95%）
4. **容错降级**：任何 Tool 失败不导致整个 session 崩溃，降级输出有明确标注
5. **性能基线**：核心工作流 wf_match_v2 端到端 ≤ 5 分钟

---

## 3. 测试范围

| 层次 | 包含 | 不包含 |
|------|------|--------|
| Tool 单元测试 | 7个Tool的输入/输出契约、确定性算法的正确性、LLM Tool 的 prompt 注入验证 | 外部 API(Tavily)的真实调用（mock） |
| Agent 行为测试 | Supervisor 路由决策、AnalysisAgent 分析质量、ReportAgent 生成+自审质量 | LLM 输出的逐字一致性 |
| 工作流集成测试 | 6条工作流的端到端链路、Tool→Agent→Gate 数据流 | 真实用户场景的性能压测 |
| Gate 校验测试 | 所有检查规则、三态决策、与 ReportAgent 的延迟问题交互 | — |
| 记忆系统测试 | STM 读/写、LTM 语义检索、consolidation 流程、衰减机制 | 大规模记忆数据下的性能 |
| Eval 回归测试 | 已有 matching/resume eval cases、检索/归因/洞察评分 | 新 eval 维度（interview/routing） |

---

## 4. 测试环境

| 维度 | 本地开发 | CI |
|------|---------|-----|
| LLM | 真实调用（qwen-plus） | Mock LLM 响应（确定性 fixture JSON） |
| Tavily | Mock（返回 fixture JSON） | Mock |
| PostgreSQL/pgvector | 本地 Docker `pgvector/pgvector:16` | CI service container |
| Redis | 本地/可选 | CI mock |
| 记忆后端 | SQLite（默认） | SQLite |
| Python | 3.11+ | 3.11, 3.12 |
| 依赖 | `requirements-minimal.txt` | 同 |
| 环境变量 | `.env` 配置 | CI secrets |
| Mock LLM 响应来源 | — | `tests/fixtures/llm_responses/` 目录下的 JSON 文件 |

---

## 5. 测试策略

### 5.1 分层策略

```
Layer 1: Gate 规则测试        ← 最先实现，纯规则，最容易验证
Layer 2: Tool 单元测试        ← 确定性 Tool 优先，LLM Tool 用 mock
Layer 3: Agent 行为测试       ← 结构化断言，不追求逐字匹配
Layer 4: 记忆系统测试         ← STM/LTM/consolidation 独立测试
Layer 5: 工作流集成测试       ← 端到端，用 fixture 组装
Layer 6: E2E 测试             ← 少量核心场景，本地跑真实 LLM
```

### 5.2 Mock 策略

- **Tavily**：`tests/fixtures/tavily/` 下的 JSON fixture，按 source_class 分类
- **LLM**：`tests/fixtures/llm_responses/` 下的 JSON fixture，按 Agent/Tool 分类
  - 每个 fixture 包含 `system_prompt_hash` + `human_prompt_hash` + `mock_response`
  - 测试中通过 `mock_llm_response(agent_name, prompt_text)` 获取对应 fixture
- **pgvector**：使用 `pytest-postgresql` 或 Docker service container
- **RAG**：`tests/fixtures/rag/` 下的 embedding 矢量 fixture

### 5.3 测试数据

- 候选人 fixture：`tests/fixtures/candidates/`（含完整 profile、稀疏 profile、空 profile）
- 简历文件 fixture：`tests/fixtures/resumes/`（PDF/DOCX/TXT/Markdown 各一份）
- JD fixture：`tests/fixtures/jds/`（完整 JD、模糊 JD、空 JD）
- Offer fixture：`tests/fixtures/offers/`（2 offer 对比、3 offer 对比）

---

## 6. 功能测试需求

### 6.1 wf_match_v2（岗位匹配）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-MATCH-01 | 正常匹配 | query + candidate_profile + resume_evidence + job_posting | JobSnapshot + MatchAssessment + 报告，overall_score 在 0-100 范围内 |
| FUNC-MATCH-02 | 仅 query 无候选人 | 仅 query | overall_score ≤ 58，含保守降级标注，risks 非空 |
| FUNC-MATCH-03 | 可疑岗位 | query + Suspicious 岗位 | 报告开头含醒目风险警告，risks 含 Suspicious 提示 |
| FUNC-MATCH-04 | must_have 缺失 | query + candidate_profile + 缺失核心技能 | recommendation ≠ strong_recommend，gaps 含 hard_blocker 项 |
| FUNC-MATCH-05 | 无 resume_evidence | query + candidate_profile 但无 evidence | overall_score ≤ 58，reasoning_notes 含保守降级说明 |

### 6.2 wf_resume_tailor_v2（简历定制）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-TAILOR-01 | 正常定制 | candidate_profile + resume_evidence + job_snapshot + match_assessment | TailoringPlan + ResumeVersion + FactCheckReport(status=passed) |
| FUNC-TAILOR-02 | 缺关键词 | 候选人技能与岗位要求不匹配 | keyword_coverage.missing 非空，fact_check_report.status ≠ rejected |
| FUNC-TAILOR-03 | blocked_claims | 存在缺失但被禁止补写的 claims | fact_check_report.status = downgraded，blocked_claims 非空 |
| FUNC-TAILOR-04 | 无 match_assessment | 缺匹配评估 | 报错或自动触发 wf_match_v2 |
| FUNC-TAILOR-05 | 空 profile | candidate_profile = {}  | 返回空 artifacts，不崩溃 |

### 6.3 wf_interview_prep_v2（面试准备）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-INTERV-01 | 正常生成 | candidate_profile + resume_evidence + job_snapshot + match_assessment | InterviewPrepPack，至少 1 条 project_deep_dive 和 1 条风险追问 |
| FUNC-INTERV-02 | 缺 match_assessment | 缺匹配评估 | 提示先生成 wf_match_v2 |
| FUNC-INTERV-03 | JD 信息弱 | job_snapshot 中技术栈信息稀疏 | 降低技术题比重，prep_pack 中明确说明 |

### 6.4 wf_profile_bootstrap（简历解析）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-PROFILE-01 | PDF 解析 | 正常 PDF 简历 | CandidateProfile + ResumeEvidence + completeness ≥ 0.5 |
| FUNC-PROFILE-02 | 文件文本过短 | 简历 < 100字符 | profile_completeness < 0.5，warnings 含 insufficient_text |
| FUNC-PROFILE-03 | 损坏文件 | 损坏的 PDF / 空文件 | parse_error，不崩溃 |
| FUNC-PROFILE-04 | TXT 解析 | 纯文本简历 | 正常输出 |
| FUNC-PROFILE-05 | 已有结构化画像 | state 中已有 candidate_profile | 跳过解析，复用已有画像 |

### 6.5 wf_offer_compare（offer 对比）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-OFFER-01 | 2 offer 对比 | 2 个完整 offer 数据 | 排名 + 对比建议，weighted_totals 含两个 offer |
| FUNC-OFFER-02 | 仅 1 个 offer | 1 个 offer | 返回错误，不崩溃 |
| FUNC-OFFER-03 | 差距极小 | 总分差距 < 3 分 | recommendation 含"差距很小"提示 |

### 6.6 Gate 功能性

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| FUNC-GATE-01 | 通过 | 全部检查项满足 | status = passed |
| FUNC-GATE-02 | 降级（证据不足） | evidence_count < min_evidence_count | status = downgraded，warning_message 非空 |
| FUNC-GATE-03 | 降级（公司特异性低） | company_specific_source_count < min | status = downgraded |
| FUNC-GATE-04 | 拒绝（虚构） | 输出含 forbidden_phrase | status = rejected |
| FUNC-GATE-05 | 拒绝（越界） | 岗位证据被写成候选人事实 | status = rejected |
| FUNC-GATE-06 | 拒绝（候选人改写） | CandidateProfile 被下游节点修改 | status = rejected |

---

## 7. Agent 行为测试需求

### 7.1 Supervisor

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| AGT-SUP-01 | 确定性路由-match | query="分析匹配度" | intent=match, workflow=wf_match_v2 |
| AGT-SUP-02 | 确定性路由-tailor | query="帮我改简历" | intent=resume_tailor, workflow=wf_resume_tailor_v2 |
| AGT-SUP-03 | 确定性路由-interview | query="准备面试" | intent=interview_prep, workflow=wf_interview_prep_v2 |
| AGT-SUP-04 | 确定性路由-offer | query="对比这两个offer" | intent=offer_compare, workflow=wf_offer_compare |
| AGT-SUP-05 | 文件上传检测 | 简历文件传入 | intent=profile_bootstrap, workflow=wf_profile_bootstrap |
| AGT-SUP-06 | LLM 路由 | query 不含确定性关键词 | LLM 返回合法 intent + query_profile，所有必填字段齐全 |
| AGT-SUP-07 | 路由回退 | LLM 超时/返回非法 JSON | 回退到确定性规则或默认 wf_match_v2 |
| AGT-SUP-08 | 缺参检测-match | wf_match_v2 选中有 candidate_profile 无 resume_evidence | 标注"无简历证据" |
| AGT-SUP-09 | 缺参检测-tailor | wf_resume_tailor_v2 选中但缺 candidate_profile | 提示先走 wf_profile_bootstrap |
| AGT-SUP-10 | intent 分类 | query="你好"（非业务意图） | intent=general, 回退到 wf_match_v2 |
| AGT-SUP-11 | query_profile 提取 | query="字节跳动后端实习" | query_profile.company="字节跳动", role="后端实习" |

### 7.2 AnalysisAgent

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| AGT-ANAL-01 | schema 符合性 | 标准 match 工作流产物 | 输出含 query_result + insight_result + quality_metrics |
| AGT-ANAL-02 | claims 证据绑定 | 标准输入 | 每个 claim 有 evidence_refs |
| AGT-ANAL-03 | 风险识别 | candidate 有明显技能缺口 | candidate_risks 非空，每条风险绑定 evidence_refs |
| AGT-ANAL-04 | 行动项绑定 | 标准输入 | action_plan_items 每个绑定至少 1 个 evidence_ref |
| AGT-ANAL-05 | 无 forbidden_phrases | 标准输入 | 输出不含 forbidden_phrases（"精通""一定过筛"等） |
| AGT-ANAL-06 | 空输入降级 | 检索证据为空 | 标记 fallback_analysis，conservative 模式 |

### 7.3 ReportAgent

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| AGT-REP-01 | section 完整性 | 标准 match 产物 | 所有必需 section 出现，非空内容 |
| AGT-REP-02 | 自审通过 | 生成内容合格 | 直接输出，无 review_feedback |
| AGT-REP-03 | 自审轻微修复 | 缺少 1 个 section | 内部修复后输出，report_content 含补充 section |
| AGT-REP-04 | 自审失败 | 严重事实矛盾 | 生成 review_feedback，含有 retry_target |
| AGT-REP-05 | 字数达标 | 标准输入 | report_content 字符数 ≥ 320 |
| AGT-REP-06 | 来源链接 | 标准输入 | 报告中 URL 数量 ≥ 2 |
| AGT-REP-07 | 模板选择 | wf_interview_prep_v2 产物 | 使用面试准备报告模板 |
| AGT-REP-08 | 模板选择 | wf_offer_compare 产物 | 使用 offer 对比报告模板 |

---

## 8. 性能与稳定性测试需求

| 编号 | 测试项 | 目标 | 方法 |
|------|--------|------|------|
| PERF-01 | wf_match_v2 端到端延迟 | ≤ 5分钟 | 计时器包裹 stream_events() |
| PERF-02 | SearchOrch Tavily 超时容忍 | 单工具 ≤ 15秒，失败不阻塞 | mock Tavily 延迟/超时 |
| PERF-03 | RAG 检索延迟 | 本地 pgvector ≤ 2秒 | 测试前预加载 fixture 数据 |
| PERF-04 | LLM 调用超时 | 单次 ≤ 60秒 | LLM invoke 配置 timeout=60 |
| PERF-05 | Gate 检查延迟 | ≤ 100ms | 所有规则一次执行计时 |
| PERF-06 | 缓存命中率 | 相同 query 重复调用命中 > 80% | search cache TTL 内重复 query |
| PERF-07 | 连续 session 内存稳定性 | 100次 session 增量 < 50MB | tracemalloc 对比前后 snapshot |
| PERF-08 | STM 读写延迟 | 单用户 ≤ 50ms | SQLite/PG 本地测试 |

---

## 9. 异常与容错测试需求

### 9.1 Tool 层异常

| 编号 | 场景 | 触发方式 | 预期 |
|------|------|---------|------|
| RES-T-01 | Tavily API 500 | mock Tavily 返回 500 | SearchOrch 记录 failure 到 search_failures，继续执行 |
| RES-T-02 | pgvector 连接断开 | RAG_DATABASE_URL 指向无效地址 | RAG 检索静默降级，rag_failures 非空，不抛异常 |
| RES-T-03 | ResumeParser LLM 非法 JSON | mock LLM 返回非 JSON 文本 | 回退到规则抽取，warnings 非空 |
| RES-T-04 | JobAnalyzer 空 evidence | evidence_items = [] | 生成保守版 JobSnapshot（仅基于 query_profile 推断） |
| RES-T-05 | MatchingEngine 空 job_snapshot | job_snapshot = {}  | 返回空 match_assessment，不崩溃 |

### 9.2 Agent 层异常

| 编号 | 场景 | 触发方式 | 预期 |
|------|------|---------|------|
| RES-A-01 | Supervisor LLM 超时 | mock LLM 延迟 70秒 | 回退到确定性路由 |
| RES-A-02 | AnalysisAgent 缺失字段 | mock LLM 返回不完整 JSON | 标记 fallback_analysis = True |
| RES-A-03 | ReportAgent 自审修复循环 | 修复 1 次后仍不合格 | 生成 review_feedback，不进入死循环 |

### 9.3 Gate 层异常

| 编号 | 场景 | 触发方式 | 预期 |
|------|------|---------|------|
| RES-G-01 | Gate 规则抛异常 | 某检查规则内部异常 | conservative 降级 + 记录 error，不阻塞交付 |

### 9.4 工作流层异常

| 编号 | 场景 | 触发方式 | 预期 |
|------|------|---------|------|
| RES-W-01 | 连续 rejected | Gate rejected 2 次 | conservative 模式，向用户明确说明 |
| RES-W-02 | 中间步骤失败 | 某 Tool 抛未捕获异常 | 从最近成功节点恢复，已确认 asset 不重复执行 |
| RES-W-03 | 记忆加载失败 | STM store 不可用 | 静默降级，memory_used = False |

### 9.5 系统级异常

| 编号 | 场景 | 触发方式 | 预期 |
|------|------|---------|------|
| RES-S-01 | 环境变量缺失 | 删除 TAVILY_API_KEY | Settings 使用默认值，不崩溃 |
| RES-S-02 | query 为空 | query="" | 返回 400，detail 含错误说明 |
| RES-S-03 | SQL 注入 pattern | query 含 SQL 注入语句 | guardrails 拦截并 block |

---

## 10. 测试用例设计

### 10.1 目录结构

```
tests/
├── tools/
│   ├── test_search_orch.py          查询词生成、去重、评分、缓存、RAG集成
│   ├── test_job_analyzer.py         JD解析、外部证据合并、原型检测、合法性评分
│   ├── test_matching_engine.py      关键词匹配、维度评分、降级规则、Suspicious感知
│   ├── test_resume_tailor.py        关键词覆盖、section actions、fact check、边界
│   ├── test_resume_parser.py        文件解析、LLM抽取、completeness计算、错误文件
│   ├── test_interview_coach.py      问题生成、evidence接地验证、JD信息弱场景
│   └── test_offer_evaluator.py      加权计算、排名、1 offer边界、差距极小
├── agents/
│   ├── test_supervisor.py           确定性路由(5)、LLM路由(2)、回退(1)、缺参检测(2)、intent分类(1)
│   ├── test_analysis_agent.py       两阶段分析、claims绑定、风险识别、行动项、降级
│   └── test_report_agent.py         section完整性、自审流程、字数检查、模板选择
├── gate/
│   └── test_gate.py                 passed(2)、downgraded(3)、rejected(3)、异常处理(1)
├── workflows/
│   ├── test_wf_match_v2.py          完整输入、仅query、可疑岗位
│   ├── test_wf_resume_tailor.py     正常定制、缺match_assessment
│   └── test_wf_profile_bootstrap.py PDF/TXT、短文本、损坏文件
├── memory/
│   ├── test_stm.py                  STM读/写、按user_id隔离、空user_id跳过
│   ├── test_ltm.py                  LTM语义检索、衰减因子、冷记忆标记
│   └── test_consolidation.py        模式提取、importance计算、去重upsert
├── resilience/
│   └── test_resilience.py           Tool失败降级、Agent回退、Gate异常、连续rejected
└── eval/
    ├── test_matching_scorer.py      已有（6 条）
    ├── test_resume_scorer.py        已有（7 条）
    └── test_eval_harness.py         已有（2 条）
```

### 10.2 各文件最少 case 数

| 文件 | 最少 case | 说明 |
|------|----------|------|
| test_search_orch.py | 6 | 正常搜索、缓存命中、RAG集成、去重、空结果、工具失败 |
| test_job_analyzer.py | 6 | 有JD、无JD、合法性高、可疑、原型确定、原型不确定 |
| test_matching_engine.py | 5 | 强匹配、有差距、无evidence、must_have缺失、Suspicious |
| test_resume_tailor.py | 5 | 正常、缺关键词、空profile、事实降级、无匹配评估 |
| test_resume_parser.py | 5 | PDF、TXT、短文本、损坏文件、已有画像跳过 |
| test_interview_coach.py | 4 | 正常生成、缺match_assessment、JD弱、evidence接地 |
| test_offer_evaluator.py | 4 | 2 offer、1 offer、差距极小、自定义权重 |
| test_supervisor.py | 11 | 确定性5、LLM2、回退1、缺参2、intent1 |
| test_analysis_agent.py | 6 | schema、claims绑定、风险、行动项、forbidden、降级 |
| test_report_agent.py | 8 | section、自审通过、修复、失败、字数、链接、模板2 |
| test_gate.py | 9 | passed2、downgraded3、rejected3、异常1 |
| test_wf_match_v2.py | 3 | 完整输入、仅query、可疑岗位 |
| test_wf_resume_tailor.py | 2 | 正常定制、缺match_assessment |
| test_wf_profile_bootstrap.py | 3 | PDF、TXT、短文本 |
| test_stm.py | 4 | 读、写、隔离、空user_id |
| test_ltm.py | 4 | 检索、衰减、冷记忆、多标签查询 |
| test_consolidation.py | 4 | 提取、importance、upsert、RAG命中关联 |
| test_resilience.py | 6 | Tool失败3、Agent回退1、Gate异常1、连续rejected1 |
| **总计** | **~95** | |

### 10.3 fixture 目录结构

```
tests/fixtures/
├── candidates/
│   ├── full_profile.json          完整 CandidateProfile
│   ├── sparse_profile.json        仅含 skills 和 target_roles
│   └── empty_profile.json         {}
├── resumes/
│   ├── sample.pdf                 正常 PDF 简历
│   ├── sample.docx                正常 DOCX 简历
│   ├── sample.txt                 正常 TXT 简历
│   ├── short.txt                  <100 字符的短简历
│   └── corrupted.pdf              损坏的 PDF
├── jds/
│   ├── full_jd.txt                完整岗位描述
│   ├── vague_jd.txt               模糊岗位描述
│   └── empty_jd.txt               空文件
├── offers/
│   ├── two_offers.json            2 个 offer 对比数据
│   └── single_offer.json          1 个 offer 数据
├── llm_responses/
│   ├── supervisor/
│   │   ├── match_intent.json      匹配意图 fixture
│   │   ├── tailor_intent.json     定制意图 fixture
│   │   └── fallback.json          回退 fixture
│   ├── analysis_agent/
│   │   ├── full_response.json     完整分析 response
│   │   └── partial_response.json  不完整 response（缺字段）
│   └── report_agent/
│       ├── match_report.json      match 报告 fixture
│       └── degraded_report.json   降级报告 fixture
├── tavily/
│   ├── company_profile.json       公司画像搜索结果
│   ├── jd_results.json            JD 搜索结果
│   ├── interview_results.json     面经搜索结果
│   └── empty_results.json         空搜索结果
└── rag/
    ├── job_chunks.json             预设的 RAG 检索结果
    └── embeddings.npy              预设的 embedding 向量
```

---

## 11. 验收标准

### P0 — 阻塞发布（必须全部通过）

- [ ] **Gate 拦截率**：所有已知 forbidden_phrases 100% 被拦截
- [ ] **工作流完整性**：wf_match_v2 + wf_resume_tailor_v2 + wf_profile_bootstrap 端到端通过（CI mock LLM）
- [ ] **容错性**：任一 Tool 失败不导致 session 崩溃
- [ ] **确定性逻辑正确性**：MatchingEngine + ResumeTailor + OfferEvaluator 所有单元测试通过
- [ ] **记忆隔离**：user_id A 无法读取 user_id B 的记忆
- [ ] **API 安全**：query="" 返回 400；SQL 注入 pattern 被 guardrails 拦截
- [ ] **所有 Gate 规则测试通过**：passed/downgraded/rejected 各场景全覆盖

### P1 — 应通过（阻塞新功能开发）

- [ ] **Supervisor 路由准确率 ≥ 85%**（11 条 Agent 行为用例中 ≥ 9 条通过）
- [ ] **ReportAgent 自审修复率 ≥ 50%**
- [ ] **连续 100 次 session 无内存泄漏**（tracemalloc 增量 < 50MB）
- [ ] **wf_match_v2 端到端延迟 ≤ 5 分钟**（本地真实 LLM）
- [ ] **Eval 回归通过**：已有 matching/resume eval cases 全部通过
- [ ] **STM 读写正确性**：memory_summary 和 artifact_refs 在 session 中正确流转

### P2 — 最好通过（不影响核心交付）

- [ ] **Supervisor 路由准确率 ≥ 90%**
- [ ] **ReportAgent 输出字数 ≥ 320**
- [ ] **缓存命中率 ≥ 80%**
- [ ] **wf_interview_prep_v2 + wf_offer_compare 端到端通过**
- [ ] **LTM consolidation 正确提取 pattern**（importance ≥ 预期值）
- [ ] **Agent 行为测试全部通过**（AnalysisAgent + ReportAgent 共 14 条）
