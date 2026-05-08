# System Architecture 规范

## 1. 目标
描述 Job Assistant 阶段二的完整系统架构。架构从阶段一的"14 节点线性图"升级为分层设计：

- **3 Agent** — 需要 LLM 自主推理和决策
- **7 Tool** — 确定性逻辑或单次 LLM 调用，不做自主决策
- **1 Gate** — 纯规则检查，0 LLM
- **6 Workflow** — Supervisor 按需选择的执行路径

## 2. 架构总览

注意：下图为概念层次示意，非精确数据流。实际每条工作流是独立的顺序执行路径（见 §4），并非所有请求都流经所有 Tool 和 Agent 层。例如 `wf_profile_bootstrap` 跳过 AnalysisAgent 和 ReportAgent，`wf_offer_compare` 跳过 AnalysisAgent。

```
                         ┌─────────────────────┐
                         │     SUPERVISOR       │  Agent
                         │ 意图路由 + 缺参检测    │
                         │ + 工作流选择          │
                         └──────────┬──────────┘
                                    │
          ┌─────────────┬───────────┼───────────┬─────────────┐
          │             │           │           │             │
          ▼             ▼           ▼           ▼             ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │wf_match  │ │wf_resume │ │wf_interv │ │wf_profil │ │wf_offer  │
    │   _v2    │ │_tailor_v2│ │iew_prep  │ │e_bootstr │ │_compare  │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │            │            │
         └────────────┼────────────┼────────────┼────────────┘
                      │            │            │
                      ▼            ▼            ▼
              ┌───────────────────────────────────────┐
              │             TOOL LAYER                │
              │  ┌─────────────┐ ┌─────────────────┐  │
              │  │SearchOrch   │ │ JobAnalyzer     │  │
              │  │(LLM查词+编排)│ │(JD解析+岗位画像  │  │
              │  │             │ │ +合法性评分)     │  │
              │  └─────────────┘ └─────────────────┘  │
              │  ┌─────────────┐ ┌─────────────────┐  │
              │  │MatchingEng  │ │ ResumeTailor    │  │
              │  │(0 LLM)      │ │ (0 LLM)         │  │
              │  └─────────────┘ └─────────────────┘  │
              │  ┌─────────────┐ ┌─────────────────┐  │
              │  │ResumeParser │ │ InterviewCoach  │  │
              │  │(LLM抽取+规则)│ │(LLM生成问题)     │  │
              │  └─────────────┘ └─────────────────┘  │
              │  ┌─────────────┐                      │
              │  │OfferEval    │                      │
              │  │(0 LLM)      │                      │
              │  └─────────────┘                      │
              └───────────────────┬───────────────────┘
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │          AnalysisAgent (Agent)         │
              │  深度分析 + 洞察 + 风险评估 + 行动项     │
              └───────────────────┬───────────────────┘
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │           ReportAgent (Agent)          │
              │  报告生成 + 自审                        │
              └───────────────────┬───────────────────┘
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │              GATE (System)             │
              │  质量阈值检查 + 事实边界校验             │
              │  输出: passed | downgraded | rejected   │
              └───────────────────┬───────────────────┘
                                  │
                              User Output
```

## 3. 分层定义

### 3.1 Agent 层（3 个）

需要 LLM 自主推理和多步决策。每个 Agent 有明确的"理解 → 推理 → 判断"链路。

| Agent | 职责 | LLM 调用 | 说明 |
|-------|------|---------|------|
| **Supervisor** | 意图识别 + 缺参检测 + 工作流选择 | 1次（有确定性回退） | 系统入口，合并原 IntentRouter |
| **AnalysisAgent** | 深度分析检索结果，识别候选人风险，生成一周行动计划 | 重度 | 合并原 QueryAgent + InsightAgent |
| **ReportAgent** | 结构化报告生成 + 内置自审 | 重度 | 合并原 ReportAgent + ReviewAgent |

### 3.2 Tool 层（7 个）

单步执行，不做自主决策。可以有 LLM 调用（如生成查询词、解析文本），但不涉及"下一步做什么"的判断。

| Tool | 职责 | LLM | 对应原 Agent |
|------|------|-----|-------------|
| **SearchOrchestrator** | 生成搜索查询词 → 并发调 Tavily/RAG → 去重合并 → 评分排序 | 1次（生成查询词） | SearchAgent |
| **JobAnalyzer** | JD解析 + 岗位画像构建 + 合法性评分 → 输出 JobSnapshot | 1次（如有 raw_jd_text） | JobIntelligenceAgent + JDParser + LegitimacyScorer |
| **MatchingEngine** | 候选人技能 × 岗位要求的纯关键词匹配 | 0 | MatchingAgent |
| **ResumeTailor** | 关键词覆盖计算 + section 改写建议 + fact check | 0 | ResumeTailorAgent |
| **ResumeParser** | 解析简历文件 → CandidateProfile + ResumeEvidence | 1次（LLM 抽取） | 原 ProfilePipeline |
| **InterviewCoach** | 基于匹配结果生成面试问题+回答框架 | 1次（LLM 生成） | InterviewCoachAgent |
| **OfferEvaluator** | 10维加权矩阵对比 | 0 | OfferEvaluator |

### 3.3 Gate 层（1 个）

纯规则检查，0 LLM 调用。可被任何工作流在交付前复用。

| 检查维度 | 规则来源 | 若失败 |
|---------|---------|--------|
| 证据充足性 | RetrievalPolicy.min_evidence_count 等 | downgraded |
| 公司特异性 | RetrievalPolicy.min_company_specific_sources | downgraded |
| 事实边界 | forbidden_phrases (如"精通""一定过筛") | rejected |
| 证据引用 | 每个结论是否有 evidence_refs | downgraded |
| 虚构检测 | 断言词是否由 ResumeEvidence 支撑 | rejected |

## 4. 工作流定义（6 条）

每条工作流是固定的节点执行序列。Supervisor 选择工作流后，WorkflowAgent 负责任务编排和恢复。

### 4.1 wf_match_v2
```
SearchOrch → JobAnalyzer → MatchingEngine → AnalysisAgent → ReportAgent → Gate
```
用户输入：query + candidate_profile(可选) + resume_evidence(可选) + job_posting(可选) + raw_jd_text(可选)
输出：JobSnapshot + MatchAssessment + 分析报告

### 4.2 wf_resume_tailor_v2
```
JobAnalyzer → MatchingEngine → ResumeTailor → AnalysisAgent → ReportAgent → Gate
```
用户输入：candidate_profile + resume_evidence + job_snapshot(可选)
输出：MatchAssessment + ResumeTailoringPlan + ResumeVersion + FactCheckReport

### 4.3 wf_interview_prep_v2
```
JobAnalyzer → MatchingEngine → InterviewCoach → AnalysisAgent → ReportAgent → Gate
```
用户输入：candidate_profile + resume_evidence + job_snapshot(可选)
输出：MatchAssessment + InterviewPrepPack

### 4.4 wf_profile_bootstrap
```
ResumeParser → Gate(profile_completeness检查)
```
用户输入：简历文件（PDF/DOCX/TXT）
输出：CandidateProfile + ResumeEvidence + profile_completeness 评分

### 4.5 wf_offer_compare
```
OfferEvaluator → ReportAgent → Gate
```
用户输入：多个 offer 数据（公司、title、薪资、期权等）
输出：OfferComparison（排名+建议）

### 4.6 wf_application_followup_v1（阶段三）
```
ApplicationStore(create/update) → Gate(status合法性检查)
```
用户输入：投递操作（创建/更新状态/追加备注）
输出：ApplicationRecord

## 5. Supervisor 路由规则

| 用户输入特征 | 选择工作流 | 缺参检查 |
|-------------|-----------|---------|
| 问"匹配度/适合吗/怎么样" + 有候选人+岗位信息 | wf_match_v2 | 缺 CandidateProfile → 提示先走 wf_profile_bootstrap |
| 问"改简历/优化简历" | wf_resume_tailor_v2 | 缺 MatchAssessment → 先跑 wf_match_v2 |
| 问"准备面试/会问什么" | wf_interview_prep_v2 | 缺 MatchAssessment → 先跑 wf_match_v2 |
| 上传简历文件, 无结构化画像 | wf_profile_bootstrap | - |
| 多个 offer 对比 | wf_offer_compare | 缺 offer 数据 → 提示提供 |
| 模糊查询（"帮我看看这个岗位"） | 默认 wf_match_v2 | 标注"信息不足，分析偏保守" |

## 6. 执行与恢复

### 6.1 幂等性
- Tool 调用结果可被缓存（相同输入 → 相同输出）
- Gate 检查可重复执行，不改变 artifact 状态

### 6.2 恢复策略
- 从最近成功节点恢复
- 按 artifact 粒度恢复：只重跑失败节点，不重复解析已确认资产
- 每次运行记录输入摘要、版本和时间戳

### 6.3 Memory 集成
- Session 开始：load_memory_for_user() → 注入历史摘要 + artifact 引用
- Session 结束：save_memory_turn() → 持久化摘要 + artifact_refs
- consolidation：周期性地将高价值 STM 记录提升为 LTM

## 7. 与阶段一的差异

| 维度 | 阶段一 | 阶段二 |
|------|--------|--------|
| 图结构 | 14节点固定线性图（服务2条工作流） | Supervisor动态选择 + 6条工作流 |
| Agent数 | 14个（5个调LLM, 9个不调） | 3 Agent + 7 Tool + 1 Gate |
| 路由 | 无（全跑） | Supervisor按需路由 |
| 缺参处理 | ResumeTailorAgent返回空结果 | Supervisor提前检测并提示 |
| Verifier | ResumeTailorAgent内嵌 FactCheckReport | 统一 Gate，所有产出均校验 |
| 简历入口 | 需预先结构化输入 | ResumeParser 支持文件上传 |
| JD入口 | 通过检索推断 | JobAnalyzer 支持直接粘贴JD解析 |
