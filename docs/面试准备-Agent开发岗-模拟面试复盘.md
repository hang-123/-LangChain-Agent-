# Agent/AI应用开发岗 模拟面试复盘

> 面试岗位：Agent开发、AI应用开发
> 项目背景：基于 LangGraph 的多 Agent 求职研究助手
> 日期：2026-05-18

---

## 一、系统架构 — Supervisor + ReAct 协调

**面试官追问**：Supervisor 能中断搜索 Agent 的内部 ReAct 循环吗？

**你的问题**：回答时夸大了 Supervisor 的能力，实际是"任务级编排"不是"步骤级调度"。

**正确说法**：
- Supervisor 的真实角色是"基于状态的流程编排器"，不是实时调度器
- 搜索 Agent 内部的 ReAct 循环对 Supervisor 不透明，只拿到最终结果
- 这是取舍：实现简单、调试清晰，代价是无法干预内部决策

**如果要改进**：
1. 共享 state channel，搜索 Agent 每轮 ReAct 后写中间状态，Supervisor 通过 interrupt 暂停
2. 去掉搜索 Agent 的独立 ReAct，Supervisor 直接以 ReAct 模式调工具

**代码位置**：`api/agents/supervisor.py`, `api/core/graph.py`

---

## 二、工作流与状态机设计

**你的回答**：提到"evidence items 不足"和"匹配度低"两种状态触发降级处理，用规则写死阈值 = 5 条。

**实际机制**：
- evidence_sufficiency 阈值是 **4 条**（`gate.py:33` `min_evidence_count=4`），不是 5
- company_specificity 阈值是 **2 个**（`gate.py:46` `min_company_specific=2`）
- 低于阈值 → Gate status = "downgraded"（不是 rejected）
- 降级后重试策略由 `root_cause` 决定回溯到哪个节点（`graph.py:356-385`）

**工作流路由**（`graph.py:193-215`）：

| 意图 | 工作流 | 节点序列 |
|---|---|---|
| match（匹配分析） | wf_match_v2 | SearchOrchestrator → JobAnalyzer → MatchingEngine → AnalysisAgent → ReportAgent → Gate |
| resume_tailor（简历定制） | wf_resume_tailor_v2 | JobAnalyzer → MatchingEngine → ResumeTailor → AnalysisAgent → ReportAgent → Gate |
| interview_prep（面试准备） | wf_interview_prep_v2 | JobAnalyzer → MatchingEngine → InterviewCoach → AnalysisAgent → ReportAgent → Gate |
| profile_bootstrap（简历解析） | wf_profile_bootstrap | ResumeParser → Gate |
| offer_compare（Offer对比） | wf_offer_compare | OfferEvaluator → ReportAgent → Gate |
| application_followup（投递管理） | wf_application_followup_v1 | ApplicationStore → Gate |

**重试路由逻辑**（`graph.py:356-385`）：
- root_cause = "retrieval" → 回溯到 SearchOrchestrator 或 JobAnalyzer
- root_cause = "attribution" → 回溯到 AnalysisAgent
- root_cause = "synthesis" → 回溯到 ReportAgent
- 超过 `max_retries` → 强制结束

---

## 三、RAG 系统

### 3.1 整体架构

**面试官追问**：RAG 和 Memory 是同一套向量库还是分开的？

**实际设计**（`api/core/rag_store.py` + `api/tools/search_orchestrator.py`）：

RAG 和 Memory 共享 **同一个 PostgreSQL 实例**（`RAG_DATABASE_URL`），但**在不同表下**：
- RAG 数据：`rag_chunks` 表（或类似命名），存外部检索证据
- Memory 数据：`conversation_turns`（STM）+ `long_term_memories` + `memory_embeddings`（LTM）

**分离原因**：
> 对话和大模型生成的信息不一定是准确的。RAG 是外部知识来源，存的是来源网站 URL、存入时间，以检索到的准确信息为准，而不是大模型生成的信息。

### 3.2 证据分类体系

检索回来的每条证据（EvidenceItem，`api/core/contracts.py:29-40`）含以下核心字段：

| 字段 | 含义 |
|---|---|
| source_class | 证据类别：jd / company_profile / interview / tech_stack / salary_culture |
| company_specific | 是否为公司/团队特异性证据（影响 Gate 校验） |
| quality_score | 质量评分 0-100 |
| freshness_score | 时效性评分 0-100 |
| url | 原始来源链接（报告引用时用） |

Source class 的用途：Gate 的 `missing_classes` 规则检查是否缺少关键类别（比如没有 JD、没有面经），缺少则 downgraded。

### 3.3 混合检索

**稠密检索（向量语义）**：BGE-M3 via SiliconFlow，1024 维向量，pgvector IVF Flat 索引

**稀疏检索（结构化过滤）**：按 source_type、company_specific、quality_score 过滤，通过

**配置参数**（`.env.example`）：
```
RAG_DENSE_WEIGHT=0.7     # 稠密检索权重
RAG_SPARSE_WEIGHT=0.3    # 稀疏检索权重
RAG_TRUST_BONUS=0.5      # 公司特异性来源额外加分
RAG_TOP_K=4              # 最终返回 top-K
ENABLE_RERANKER=0        # Reranker 开关（当前关闭）
```

### 3.4 RAG Writeback — 搜索结果自动回写

`search_orchestrator.py:34-40`：搜索完成后自动将高质量结果写回 RAG 库：
```
ENABLE_RAG_WRITEBACK=1
RAG_WRITEBACK_QUALITY_THRESHOLD=70    # 质量分 >= 70 才回写
```

这保证了每次搜索都在丰富 RAG 知识库，下次同类查询命中率更高。

### 3.5 面试回答框架
> "RAG 和 Memory 共享同一个 PostgreSQL/pgvector 实例但表结构独立。RAG 存外部检索证据（来源 URL、source_class、时效性），Memory 存对话历史。分离是因为两者的可信度不同——RAG 以检索到的真实信息为准，Memory 里的大模型生成内容可能有偏差。RAG 的混合检索稠密权重 0.7、稀疏 0.3、公司特异性来源有 trust_bonus 加成。每次搜索后自动把高质量结果（≥70 分）写回 RAG。"

---

## 四、Memory 系统

### 4.1 STM（短期记忆）

**你的问题**：说"STM 只存最近 3 条" — **错**。

**实际**（`api/core/memory/stm_store.py`）：

- `save_turn()` 无条件 INSERT，**不限数量**，所有对话轮次全部持久化
- `load_turns()` 默认 limit=20，但在 `retrieval.py:167` 检索时显式传 `limit=3`，只取最近 3 条注入 Agent 上下文
- Session 结束后调用 `end_session()` 标记为 completed，之后不再被检索

**数据结构**：`conversation_turns` 表（PostgreSQL）

```sql
id, user_id, session_id, run_id, query,
summary_json (TurnSummary 结构化压缩),
artifacts_json, memory_tags, created_at
```

**TurnSummary 结构**（`models.py:75-88`）：`query, company, role, archetype, overall_score, recommendation, key_findings, artifacts, tags, quality_mode`

### 4.2 LTM（长期记忆）

**你的问题**：说"用户多次提及某个信息时会被持久化进 LTM" — **错**。

**实际机制**（`consolidation.py` + `ltm_store.py`）：

**(1) 存储策略：全量入库，没有"多次提及才晋级"逻辑**

- `consolidate_session()` 在 Session 结束时执行：遍历 STM 所有 turns → 重要性打分 → 分数 ≥ 0.2 → 存入 LTM
- 每轮对话存为**独立一条** LTM 记录，不跨轮合并
- 没有语义去重——说 10 次"想去字节"就是 10 条记录

**(2) 重要性打分**（`consolidation.py:24-52`）：
```
score >= 4.0 (高匹配)     → base = 0.8
score >= 3.0 (中匹配)     → base = 0.5
score < 3.0 (低匹配)      → base = 0.3
key_findings >= 3条       → +0.05
quality_mode = conservative → +0.1
```

**(3) 5 种记忆类型**（`models.py:14-37`）：

| 类型 | 含义 | 生命周期 |
|---|---|---|
| ENTITY_KNOWLEDGE | 公司/岗位的可验证事实 | 180天 |
| PATTERN | 用户行为特征 | 180天 |
| PREFERENCE | 用户偏好（显式/隐式） | 永不过期 |
| SEMANTIC | 行业通用知识 | 120天 |
| EPISODIC | 单次调研记录和结论 | 60天 |

**(4) 时间驱动衰减**（`consolidation.py:56-70`）：
```
importance = initial × max(0, 1 - days_elapsed / lifetime_days)
```
- 不是按调用次数衰减，而是**按时间线性衰减**
- 不同类型有不同的 lifetime，衰减速度不同

**(5) 检索频率 Boost**（`ltm_store.py:250-255`）：
```python
access_count >= 3 → importance × 1.1   # 被频繁检索的记忆获得加成
access_count == 0 → importance × 0.9   # 从未被访问的记忆加速衰减
```

**(6) 到期清理**（`ltm_store.py:258-268`）：
- `importance < 0.1` 且 `expires_at < now()` → 删除

### 4.3 Memory 检索管道

**四步混合检索**（`api/core/memory/retrieval.py:101-223`）：

```
Step 1: 结构化过滤  → filter by user_id + min_importance(0.2) + 关键词评分
Step 2: 向量语义搜索 → pgvector cosine similarity (可选)
Step 3: STM 近期上下文 → load_turns(limit=3) + 转换为 synthetic LTM
Step 4: RRF 融合      → Reciprocal Rank Fusion (k=60)
        ↓
      Reranker → Final score = 0.5×relevance + 0.3×importance + 0.2×recency_boost
        ↓
      按类型分组（5 种 MemoryType 各自分桶）→ 分布式注入不同 Agent 节点
```

**类型分组注入规则**（`models.py:170-185`）：

- entity_knowledge → SearchAgent query expansion
- pattern → Supervisor routing
- preference → Supervisor + Gate
- semantic → AnalysisAgent / ReportAgent
- episodic → MemoryRetrievalNode context block

### 4.4 STM vs LTM 分离原因

不是"一个存 3 条一个存全量"——两者都是全量。分离是基于**访问模式不同**：

| 维度 | STM | LTM |
|---|---|---|
| 查询方式 | `ORDER BY created_at DESC LIMIT N` | 混合检索（结构化+关键词+向量+RRF） |
| 索引需求 | 单列索引 (user_id, created_at) | 复合索引 + pgvector IVF Flat |
| 数据结构 | query + 完整 TurnSummary JSONB | 自然语言 content + importance + 向量 embedding |
| 生命周期 | Session 结束 → consolidation → 不再查 | 长期存活，时间衰减淘汰 |
| 写入频率 | 每轮对话写一次 | Session 结束时批量写入 |

**面试回答**：
> "分开是基于读写模式分离——STM 高频写入、按时间序读取的热数据，不需要向量索引；LTM 低频批量写入、按语义检索的温数据，依赖 pgvector 混合搜索。合表会让 LTM 向量索引污染 STM 的简单 OLTP 查询。这是 CQRS 在记忆系统里的应用。"

### 4.5 面试总结：STM 纠正版本
> "STM 存储所有会话轮次不做数量限制，但在检索注入 Agent 上下文时只取最近 3 条，避免上下文过长稀释注意力。LTM 是全量入库后通过时间衰减 + 检索频率 boost 淘汰低价值记忆，没有'多次提及晋级'逻辑——我之前面试时这个表述不准确。"

---

## 五、防幻觉体系 — 三层架构

**你的问题**：描述了不存在的"审查 Agent"，把规则引擎说成了 Agent。

**实际三层**：

### 第一层：Gate（纯规则，0 LLM）— `api/core/gate.py`
| 级别 | 规则 | 触发条件 |
|---|---|---|
| Rejected | forbidden_phrases | 输出含"你一定行"等禁止断言 |
| Rejected | candidate_fact_boundary | 岗位侧信息写成候选人事实 |
| Rejected | fiction_detection | 数字指标在简历证据中找不到 |
| Downgraded | evidence_sufficiency | 证据 < 4 条 |
| Downgraded | company_specificity | 公司特异来源 < 2 个 |
| Downgraded | evidence_refs | 结论缺少证据引用 |
| Downgraded | claim_evidence_coverage | 覆盖率 < 70% |
| Downgraded | action_plan_source_coverage | 行动项覆盖率 < 60% |
| Downgraded | missing_classes | 缺关键证据类别 |

### 第二层：Report Rule Checker — `api/review/rule_checker.py`
- 必填 section 缺失检测
- Markdown 章节数/字数/技术栈覆盖/URL 引用/行动清单模板化检测
- 公司特异性（公司提及次数、业务域线索覆盖）
- 质量分：每个问题 -10，满分 100

### 第三层：LLM Mild Review — `report_agent.py:_mild_llm_review()`
- 仅当前两层发现警告时才触发
- 检查内容空洞（hollow_sections）+ 矛盾陈述（contradictions）
- 由 `ENABLE_REPORT_LLM_SELF_REVIEW` 控制

### 额外：AnalysisAgent built-in fallback — `analysis_agent.py`
- LLM 调用失败 → 自动切换 heuristic 保守规则
- heuristic 里写死："所有结论都必须标清证据来源；没有证据的地方明确写'暂不能判断'"
- `temperature=0.1`（分析侧低温度减少幻觉）

---

## 六、幻觉效果度量

**你的问题**：无法回答"幻觉降低率是多少"。

**实际有的**：
- 8 维评测体系（`api/evals/harness.py`）：检索/归因/洞察/报告合规/匹配/简历/面试/路由
- CI eval + diff 回归检测（`.github/workflows/ci-eval.yml`）
- 但没有直接的"幻觉率"数字

**没有的**：
- 人工标注 ground truth 逐句对照
- fiction_detection 命中率长期追踪
- RAGAS faithfulness 等无标注度量

**正确回答**：
> "不追求精确幻觉率（需要业务专家标注，ROI 不高），而是用代理指标和自动化回归保证不倒退。Gate 的 rejected/downgrade rate 作为可比指标，每次改动后跑 eval diff 看异常波动。另外简历真实性是 P0——resume 维度的 fiction_detection 一旦命中直接 0 分。"

---

## 七、部署

**你的问题**：编造了不存在的 Redis checkpointer 和异步任务队列。

**实际部署**：
- Dockerfile: Python 3.12-slim, uvicorn, port 9000
- docker-compose: app + postgres(pgvector/pg16) + redis(7-alpine) 三容器
- `builder.compile()` — 无 checkpointer 参数，内存模式 (`api/core/graph.py:495`)
- FastAPI 直接 `graph.astream_events()` — 无 Celery/任务队列 (`api/core/executor.py:170`)
- 重启 = 任务丢失，无恢复能力

**没有的东西**：nginx 反代、SSL/域名、checkpoint 持久化、health check 端点、多副本、监控面板

**Redis 的实际用途**：缓存（ENABLE_CACHE 控制，但当前默认关闭）

**正确回答框架**：

部署：
> "Docker Compose 三容器编排，`docker-compose up -d` 一键启动。PG+pgvector 统一管理 RAG 向量、Memory、业务数据。没有 nginx、K8s、生产化配置。Demo 阶段够用。"

质量保障（系统设计，不是部署）：
> "CI eval gate：PR 触发 8 维评分 + baseline diff，低于 75 分拦截。"

可观测（系统设计，不是部署）：
> "OpenTelemetry 全链路 + NodePerfTracker 节点级性能追踪。"

---

## 八、配置化

**你的问题**：误以为"配置化 = 用户交互界面"。

**实际**：pydantic-settings + .env，开发者改配置文件调行为，没有用户界面。

**40+ 配置参数覆盖**（`api/core/settings.py`）：
- LLM: model_name, analysis_temperature(0.3), report_temperature(0.5) — 分析/报告独立调参
- 检索: RAG_TOP_K, TAVILY_MAX_RESULTS, RAG_DENSE_WEIGHT, RAG_SPARSE_WEIGHT
- 重试: MAX_RETRIES, RetryPolicy.max_retries
- 熔断: cost_per_run_cap, monthly_budget
- Memory: STALE_IMPORTANCE, SOFT_DELETE_IMPORTANCE, REFRESH_MAX_RETRIES
- 质量门: min_claim_evidence_coverage, min_action_plan_source_coverage
- Embedding: provider, model, dim (1024)
- 实验: experiment_id, rollout_pct, variants (control/treatment)

**策略类分层**（`api/core/policies.py`）：
- `RetrievalPolicy` — 证据数量/特异来源/缓存 TTL
- `QualityPolicy` — 归因覆盖率/报告质量阈值
- `RetryPolicy` — 重试上限 + 每种 issue 的目标回溯节点
- `ReportPolicy` — 报告结构/必填 section/polish 开关

**面试回答**：
> "不是简单的读 .env，而是识别出哪些参数应该独立控制。比如 ANALYSIS_TEMPERATURE=0.3 和 REPORT_TEMPERATURE=0.5 分开，因为分析阶段要低温减少幻觉，报告阶段要稍高温增加表达多样性。配置化的价值在于分离关注点，不是做了个页面。"

---

## 九、简历优化

### 改前：
```
- 基于 LangGraph 实现 Supervisor 模式的多 Agent 协同架构
- 完成 RAG 检索增强生成系统和 Memory 记忆系统的搭建
- 引入质量校验机制，降低系统幻觉
- 将模型参数、检索 top-k、重试次数和熔断阈值配置化
- 完成前后端分离，Docker 容器化部署
```

### 改后：
```
项目：基于 LangGraph 的多 Agent 求职研究助手  |  独立开发
技术栈：LangGraph / LangChain / FastAPI / PostgreSQL + pgvector / React / Docker

- 基于 LangGraph StateGraph 实现 Supervisor 模式的多 Agent 编排，
  确定性规则优先路由 + LLM 兜底，6 种意图自动分发到对应工作流，
  证据不足/归因缺失时自动降级并精准回溯到上游节点重试

- 设计双层知识架构：RAG 层管理外部检索证据（pgvector 混合检索，
  稠密/稀疏权重可调 + 公司特异性 trust bonus），Memory 层维护
  对话记忆（STM 全量存储 + LTM 5 类型分级 + 时间衰减淘汰），
  两层独立索引、检索时 RRF 融合注入 Agent 上下文

- 构建三层防幻觉体系：Gate 纯规则校验（禁止断言词 + 数字真实性 +
  claim 证据覆盖率 ≥ 70%），Rule Checker 报告结构审查，
  LLM Mild Review 轻审复查；AnalysisAgent LLM→heuristic fallback
  故障自动切换，低温 inference（0.1）减少事实性失真

- 建立 CI 自动化回归评测：8 维评分体系，每次 PR 与 main baseline
  diff 对比，低于 75 分自动拦截合入

- 系统行为策略层驱动：40+ 配置参数集中管控，分析侧/报告侧独立调参，
  检索/归因/重试/报告 4 层策略独立配置

- Docker Compose 三容器一键部署（app + PG/pgvector + Redis），
  前端 React + Tailwind + SSE 流式响应
```

---

## 十、核心面试教训

1. **不知道就说不知道**，然后讲你知道的。编造一次被拆穿 > 十个"我不确定"
2. **代码才是真相**，你说的话如果跟代码对不上，面试官一追问就崩
3. **别把不同层次的东西混在一起**。部署、质量保障、可观测是三个独立话题
4. **每句话都要经得起"为什么"追问**。比如"为什么 STM 和 LTM 分表？"
5. **没用到的技术不要提**。Redis 没用就别写，否则面试官一问就露馅
6. **Agent ≠ 规则引擎**。Gate 是纯规则函数，别叫它"审查 Agent"
7. **"配置化"的价值在于识别出哪些参数应该分开控制**，不是"能读 .env 文件"
8. **RAG 和 Memory 分开的原因不是数量差异，是可信度差异和访问模式差异**
9. **说数字之前先确认**。阈值是 4 不是 5，retrieval limit 是 3 但存储是全量
10. **没有的东西诚实说没有**，然后补充"如果要生产化，方案是什么"
