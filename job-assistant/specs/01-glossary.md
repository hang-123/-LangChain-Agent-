# 术语表

## 架构概念

### Agent
架构中需要 LLM 自主推理和多步决策的组件。系统中有 3 个 Agent: Supervisor, AnalysisAgent, ReportAgent。

### Tool
单步执行的确定性组件。可以有 LLM 调用（如文本解析、查询词生成），但不做"下一步做什么"的自主决策。系统中有 7 个 Tool。

### Gate
系统级规则检查组件，0 LLM 调用。统一所有工作流的交付前质量闸门和事实边界校验。

### Workflow
由 Supervisor 按需选择的固定执行路径。系统中有 6 条工作流。

### Supervisor
系统入口 Agent。负责意图识别、缺参检测、工作流选择。

### SearchOrchestrator (Tool)
搜索编排工具。生成查询词 → 并发调用 Tavily/RAG → 去重合并 → 评分排序。单次 LLM（生成查询词）。

### JobAnalyzer (Tool)
岗位分析工具。消费 JD 文本或检索证据，输出 JobSnapshot + ExternalEvidencePack。内置 LegitimacyScorer（合法性评分）。

### MatchingEngine (Tool)
匹配引擎。候选人技能 × 岗位要求的纯关键词匹配。0 LLM 调用。

### ResumeTailor (Tool)
简历定制工具。关键词覆盖计算 + section 改写建议 + 内置 fact check。0 LLM 调用。

### ResumeParser (Tool)
简历解析工具。解析 PDF/DOCX/TXT → CandidateProfile + ResumeEvidence。单次 LLM 抽取。

### InterviewCoach (Tool)
面试准备工具。基于匹配结果生成面试问题 + 回答框架。单次 LLM 生成。

### OfferEvaluator (Tool)
多 offer 对比工具。10维加权矩阵对比。0 LLM 调用。

### AnalysisAgent (Agent)
核心分析 Agent。消费检索证据和工具产物，生成深度分析、候选人风险、面试官期待和一周行动计划。

### ReportAgent (Agent)
报告生成 Agent。结构化报告生成 + 内置自审。

### Gate (System)
质量守门系统。统一检查证据充足性、公司特异性、事实边界、证据引用和虚构检测。0 LLM。

---

## 核心领域术语

### CandidateProfile
由简历解析得到的结构化候选人画像。

### JD
Job Description，职位描述。

### Must-have
岗位硬性要求。缺失会显著影响匹配判断。

### Nice-to-have
岗位加分项。缺失不一定阻止投递。

### Match Score
岗位与候选人的匹配度分数，范围 0-100。

### Gap
候选人与岗位要求之间的差距项。

### Risk
可能影响投递成功率或面试表现的风险项。

### Evidence
结论对应的原始依据，来源于简历内容或 JD 文本。

### Application Record
一条岗位投递记录，包含状态、时间、备注和下一步动作。

### ExternalEvidencePack
岗位侧外部证据集合，包含真实 JD、公司画像、面经和技术栈线索及其来源信息。

### JobSnapshot
供匹配、简历定制、面试准备共用的岗位快照，由 `JobPosting`、`JobRequirement` 和 `ExternalEvidencePack` 组成。

### VerificationReport
交付前验证结果，记录某个 artifact 是否通过、降级或被打回。

### WorkflowState
一次工作流运行中的共享状态对象。结构分为 `background`、`working_set`、`artifacts`、`control` 和 `telemetry` 五层。

### Background
工作流中的稳定背景信息，例如用户请求、岗位画像、候选人事实和运行策略。节点可以按需读取，但不应无差别注入所有 prompt。

### Working Set
链路中间数据，例如检索证据、分析结果和审查反馈。服务当前链路，不等同于最终交付产物。

### Artifact
可交付、可展示、可评测的业务产物，例如 `JobSnapshot`、`MatchAssessment`、`ResumeVersion`。

### Control State
工作流编排信号，例如重试次数、质量模式、降级提示、根因分类和运行状态。

### JobDocument
可入库到 RAG 的岗位侧资料，只包含 JD、公司画像、面经、技术栈和薪资文化资料。

### JobChunk
`JobDocument` 切分后的检索片段，带 metadata、source 引用和 embedding。

### Conversation Memory
按 `user_id` 保存的会话摘要和 artifact 引用，用于续接上下文，不等于完整聊天记录。

### Artifact Ref
对历史业务产物的轻量引用，例如 `job_snapshot_id`、`match_assessment_id`、`resume_version_id`。

---

## Career-Ops 集成术语

### Archetype
岗位原型分类。六种类型: AI Platform / LLMOps, Agentic / Automation, Technical AI PM, AI Solutions Architect, AI Forward Deployed, AI Transformation。

### ArchetypeDetection
岗位原型检测结果。包含 primary archetype、secondary、confidence、keyword_matches 和 reasoning。

### LegitimacyTier
岗位合法性三档分级: High Confidence, Proceed with Caution, Suspicious。

### LegitimacyAssessment
岗位合法性评估结果。包含 posting_age_days、apply_button_active、tech_specificity_score、requirements_realism_score、layoff_signals 等信号。

### Ghost Job
虚假招聘岗位。可能长期挂出、技术栈描述模糊、或公司实际不招人。

### OfferComparison
多 offer 10维加权矩阵对比结果。维度包括 north_star_alignment、cv_match、seniority、compensation、growth、remote_quality、company_reputation、tech_stack、speed、culture。

### STAR Story
STAR+R 面试故事。包含 Situation、Task、Action、Result、Reflection。Reflection 区分资深候选人和初级候选人。

### AdaptiveFraming
基于 Archetype 的自适应叙事角度。同一段经历根据目标岗位原型展示不同侧重点。

---

## 记忆系统术语

### STM (Short-Term Memory)
短期记忆。同一 session 内的多轮对话上下文。v2.0 起仅使用 PostgreSQL，按 session 隔离。

### LTM (Long-Term Memory)
长期记忆。跨 session 的持久记忆。PostgreSQL + pgvector 向量检索。v2.0 新增 5 类记忆分类、时间驱动衰减和软删除。

### MemoryType
记忆类型（v2.0 5 分类）：`entity_knowledge`（公司事实）、`pattern`（用户特征）、`preference`（用户偏好）、`semantic`（行业知识）、`episodic`（单次研究记录）。

### MemoryStatus
记忆状态（v2.0）：`active` → `expired_pending_refresh` → `soft_deleted` → 物理删除。

### Consolidation
记忆巩固。Session 结束时将高价值 STM 记录提升为 LTM。v2.0 设置 `lifetime_days` 和 `expires_at`，基于时间驱动衰减。

### Stale-While-Revalidate
软删除策略（v2.0）。到期记忆不是直接删除，而是触发 Web 搜索验证：内容变化→更新；内容不变→重置过期；刷新失败→软删除。

### MemoryHit
记忆命中。从 STM 或 LTM 检索到的相关历史记录。v2.0 按 memory_type 分组，分发到不同 agent。

### Working Memory
工作记忆。当前 AgentState 中的即时上下文，不持久化。

### RAG
检索增强生成。Tavily 网络搜索结果的 pgvector 缓存。v2.0 使用 BGE-M3 嵌入（1024d），支持 Dense+Sparse 混合检索和自动回写。

### RAG ↔ LTM Bridge
RAG 与 LTM 的桥接机制（v2.0）。高置信度 RAG 命中（quality≥80, freshness≥70）自动写入 LTM 作为 `entity_knowledge` 记忆。

### EmbeddingBackend
嵌入模型抽象层（v2.0）。支持 SiliconFlow BGE-M3 / DashScope / OpenAI 多后端切换。
