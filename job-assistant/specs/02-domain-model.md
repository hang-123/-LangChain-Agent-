# 领域模型

## 1. 设计目标
- 为所有 Agent、Tool、Eval 提供统一数据语言。
- 保证系统始终区分事实、推断、建议。
- 让任何结论都能追溯到简历、JD 或用户显式输入。
- 涵盖 career-ops 集成实体和记忆系统实体。

## 2. 实体定义

### 2.1 CandidateProfile
候选人的长期稳定画像，由简历解析结果和用户补充信息组成。

### 2.2 ResumeAsset
候选人上传或维护的一份原始简历资产。

### 2.3 ResumeEvidence
从简历中抽取出的原始证据片段，供匹配、改写、面试分析引用。

### 2.4 JobPosting
目标岗位的标准化对象，可由 JD 文本、招聘页面复制内容或手动录入生成。

### 2.5 JobRequirement
从 JD 中抽取出的结构化要求，是匹配分析的最小比较单元。

### 2.6 MatchAssessment
候选人与岗位的一次结构化匹配分析结果。

### 2.7 ResumeTailoringPlan
针对单个岗位生成的简历优化计划。

### 2.8 ResumeVersion
一份面向特定岗位的简历输出版本。

### 2.9 InterviewPrepPack
围绕某个岗位生成的一组面试准备材料。

### 2.10 ApplicationRecord
单条投递记录，面向投递流程管理。

### 2.11 ExternalEvidencePack
岗位侧外部证据集合。

### 2.12 JobSnapshot
面向下游匹配和生成任务的岗位快照。

### 2.13 VerificationReport
交付前验证结果。

### 2.14 WorkflowState
一次工作流运行的共享状态对象。

### 2.15 JobDocument
可进入 RAG 索引的岗位侧资料。

### 2.16 JobChunk
`JobDocument` 的向量检索片段。

### 2.17 ConversationMemory
按用户隔离的对话保留对象。

### 2.18 ArchetypeDetection
岗位原型检测结果，由 JobAnalyzer 在岗位分析时生成。

```json
{
  "primary": "AI Platform / LLMOps",
  "secondary": "Agentic / Automation",
  "confidence": 0.82,
  "keyword_matches": ["evals", "production ai", "observability"],
  "reasoning": "岗位描述强调 AI 评估框架和生产化，主判为 LLMOps；同时提及 multi-agent 编排，副判为 Agentic。"
}
```

### 2.19 LegitimacyAssessment
岗位合法性评估结果，由 JobAnalyzer 内置的 LegitimacyScorer 生成。独立于匹配评分。

```json
{
  "tier": "Proceed with Caution",
  "posting_age_days": 45,
  "apply_button_active": true,
  "tech_specificity_score": 0.65,
  "requirements_realism_score": 0.78,
  "layoff_signals": [],
  "repost_count_90d": 3,
  "signals_table": [
    {
      "signal_name": "posting_freshness",
      "finding": "岗位已发布45天，超出同类型中位天数",
      "weight": "Concerning",
      "reliability": "High"
    }
  ],
  "context_notes": "技术栈描述偏通用，但仍有明确的框架要求，建议投递前确认岗位仍然开放。",
  "batch_mode": false
}
```

### 2.20 MatchGap
匹配分析中的单条差距项，按四级严重度分类。

```json
{
  "description": "缺少分布式系统设计深度证据",
  "severity": "significant",
  "adjacent_experience": "有单机并发优化经验",
  "portfolio_coverage": null,
  "mitigation_plan": "可在简历中补充微服务拆分相关项目描述"
}
```

### 2.21 OfferComparison
多 offer 对比结果，10维加权矩阵。

```json
{
  "dimensions": {
    "north_star_alignment": 0.25,
    "cv_match": 0.15,
    "seniority_level": 0.15,
    "compensation": 0.10,
    "growth_trajectory": 0.10,
    "remote_quality": 0.05,
    "company_reputation": 0.05,
    "tech_stack_modernity": 0.05,
    "speed_to_offer": 0.05,
    "cultural_signals": 0.05
  },
  "scores": {
    "offer_a": {"north_star_alignment": 85, "cv_match": 78, "seniority_level": 70, "compensation": 65, "growth_trajectory": 80, "remote_quality": 90, "company_reputation": 75, "tech_stack_modernity": 85, "speed_to_offer": 60, "cultural_signals": 70},
    "offer_b": {"north_star_alignment": 70, "cv_match": 85, "seniority_level": 80, "compensation": 85, "growth_trajectory": 65, "remote_quality": 50, "company_reputation": 85, "tech_stack_modernity": 70, "speed_to_offer": 90, "cultural_signals": 80}
  },
  "weighted_totals": {"offer_a": 76.2, "offer_b": 75.5},
  "ranking": ["offer_a", "offer_b"],
  "recommendation": "offer_a 在北极星对齐和成长性上更优，offer_b 薪酬和职级更高。若长期发展优先选 offer_a，若短期收益优先选 offer_b。"
}
```

### 2.22 STARStory
STAR+R 面试故事，Reflection 字段区分资深与初级候选人。

```json
{
  "story_id": "star_001",
  "title": "订单系统 Redis 缓存优化",
  "situation": "订单查询接口在高并发场景下响应时间超过 500ms",
  "task": "优化接口性能，将 P99 控制在 200ms 以内",
  "action": "引入 Redis 缓存层，设计多级缓存策略，对热点数据做预加载",
  "result": "P99 响应时间降至 120ms，高峰期支撑 2000 QPS",
  "reflection": "如果重新做，会先分析缓存击穿和雪崩的防护方案，而不是上线后才补。另外监控指标应前置到设计阶段。",
  "archetypes": ["AI Platform / LLMOps"],
  "tags": ["缓存设计", "性能优化", "Redis"]
}
```

### 2.23 AdaptiveFraming
基于 Archetype 的自适应叙事角度。同一段经历根据目标岗位原型展示不同侧重点。

```json
{
  "archetype": "AI Platform / LLMOps",
  "headline": "具备生产化 AI 基础设施经验的候选人",
  "emphasize": ["可观测性建设", "性能指标", "系统可靠性"],
  "de_emphasize": ["前端经验", "单纯 CRUD 业务"],
  "proof_point_priority": ["缓存性能优化指标", "系统设计思路"]
}
```

### 2.24 TurnSummary
单轮对话摘要，用于 STM 存储和记忆续接。

```json
{
  "query": "帮我分析字节后端实习是否匹配",
  "artifacts": {
    "job_snapshot_id": "js_001",
    "match_assessment_id": "match_001",
    "resume_version_id": "resume_v_001"
  }
}
```

### 2.25 ConversationSession
单次会话记录，STM 的存储单元。

```json
{
  "session_id": "sess_001",
  "user_id": "user_001",
  "status": "active",
  "turns": [],
  "created_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:30:00Z"
}
```

### 2.26 LongTermMemory
跨 session 的长期记忆条目，存储于 PostgreSQL + pgvector（v2.0）。

```json
{
  "memory_id": "ltm_001",
  "user_id": "user_001",
  "memory_type": "entity_knowledge",
  "content": "字节跳动 后端实习 技术栈: Go/Python, 面试侧重系统设计",
  "embedding": [],
  "structured_data": {"company": "字节跳动", "role": "后端开发实习", "source_type": "rag_writeback"},
  "initial_importance": 0.70,
  "importance": 0.65,
  "lifetime_days": 180,
  "access_count": 3,
  "status": "active",
  "content_hash": "a1b2c3d4e5f6",
  "refresh_attempts": 0,
  "created_at": "2026-05-08T10:00:00Z",
  "last_accessed_at": "2026-05-18T12:00:00Z",
  "last_refreshed_at": null,
  "expires_at": "2026-11-04T10:00:00Z"
}
```

---

## 3. 枚举定义

### 3.1 基础枚举
- `requirement_level`: `must_have`, `nice_to_have`, `bonus`
- `evidence_type`: `education`, `work_experience`, `project`, `skill`, `certificate`, `user_input`
- `recommendation`: `strong_recommend`, `recommended_with_risks`, `neutral`, `not_recommended`
- `application_status`: `draft`, `planned`, `applied`, `screening`, `written_test`, `interviewing`, `offer`, `rejected`, `withdrawn`

### 3.2 Archetype（岗位原型）
- `AI Platform / LLMOps`
- `Agentic / Automation`
- `Technical AI PM`
- `AI Solutions Architect`
- `AI Forward Deployed`
- `AI Transformation`

### 3.3 LegitimacyTier（合法性分级）
- `High Confidence`
- `Proceed with Caution`
- `Suspicious`

### 3.4 GapSeverity（差距严重度）
- `hard_blocker`: 硬性门槛，缺失则强烈不推荐
- `significant`: 重要差距，可能影响面试表现
- `nice_to_have`: 加分项缺失
- `soft`: 轻微差异，不影响投递建议

### 3.5 OfferDimension（offer 对比维度）
- `north_star_alignment`, `cv_match`, `seniority_level`, `compensation`, `growth_trajectory`, `remote_quality`, `company_reputation`, `tech_stack_modernity`, `speed_to_offer`, `cultural_signals`

### 3.6 MemoryType（记忆类型 — v2.0 5 分类）
- `entity_knowledge`: 特定公司/岗位的可验证事实（技术栈、面试风格），180 天衰减
- `pattern`: 从多次行为中提取的用户特征（后端方向、Java 栈），180 天衰减
- `preference`: 用户显式或隐式表达的偏好（只看北上广深），永不过期
- `semantic`: 行业通用知识、面试方法论，120 天衰减
- `episodic`: 单次研究的记录和结论，60 天衰减

### 3.7 MemoryStatus（记忆状态 — v2.0 状态机）
- `active`: 正常检索，全权重
- `expired_pending_refresh`: importance ≤ 0.2，触发异步刷新（entity_knowledge / semantic）
- `refresh_failed`: 刷新失败但未达重试上限
- `soft_deleted`: importance ≤ 0.1，不可检索，30 天后物理删除

### 3.7 FollowupUrgency（跟进紧急度）
- `urgent`, `overdue`, `waiting`, `cold`

---

## 4. 实体关系
- 一个 `JobSnapshot` 可关联一个 `ArchetypeDetection`
- 一个 `JobSnapshot` 可关联一个 `LegitimacyAssessment`
- 一个 `CandidateProfile` 可关联多条 `LongTermMemory`
- 一个 `user_id` 可关联多个 `ConversationSession`，每个 session 包含多个 `TurnSummary`
- 一个 `JobRequirement` 可在 `MatchGap` 中被标注为差距

## 5. 领域不变量
- `ArchetypeDetection.confidence` < 0.5 时，结果应标注为"不确定"
- `LegitimacyAssessment.tier = Suspicious` 时，匹配分析必须附带醒目的风险警告
- `LegitimacyAssessment.batch_mode = true` 时，freshness 相关信号标记为"未验证"
- `OfferComparison` 的加权总分必须基于所有维度计算，不得有维度漏计
- `STARStory.reflection` 为空的候选人被视为"初级叙事水平"
- `LongTermMemory.importance` 按时间驱动线性衰减：`initial_importance × max(0, 1 - days_elapsed / lifetime_days)`（v2.0）
- `importance ≤ 0.2` 标记为 `expired_pending_refresh`，触发 stale-while-revalidate 刷新
- `importance ≤ 0.1` 标记为 `soft_deleted`，30 天后物理删除
- `preference` 类型永不过期
- Gate 拒绝（rejected）的 artifact 不得出现在任何用户可见输出中
