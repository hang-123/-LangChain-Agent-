# 对话记忆规范

> 最后更新: 2026-05-18 | 版本: v2.0

## 1. 目标
为 Job Assistant 提供完整的跨 session 记忆系统，包含四层架构：

1. **Session Memory** — 当前会话元数据（ConversationSession）
2. **Short-Term Memory (STM)** — 同一 session 内多轮对话的完整记录
3. **Long-Term Memory (LTM)** — 跨 session 持久记忆，带向量检索、时间驱动衰减和软删除
4. **Working Memory** — 当前 session 的即时上下文（AgentState，不持久化）

## 2. 四层架构与数据流

```
┌──────────────────────────────────────────────────────────────┐
│ Session Start                                                │
│   load_memory_for_user(user_id)                              │
│   → 加载最近一轮 TurnSummary 快照                             │
│   → 注入 state["memory_summary"]                             │
│   → 前端 meta event 展示上次研究摘要                          │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ Graph: MemoryRetrievalNode（Supervisor 之后，Search 之前）    │
│                                                              │
│   ┌─ STM 部分 ──────────────────────────────────┐           │
│   │ stm_store.load_turns(limit=3)                │           │
│   │ → 最近 3 轮转为 synthetic LongTermMemory      │           │
│   │ → score × 0.9（比 LTM 略降权）               │           │
│   └──────────────────────────────────────────────┘           │
│                                                              │
│   ┌─ LTM 结构化检索 ────────────────────────────┐           │
│   │ search_by_user(importance≥0.2, limit=top_k×3)│           │
│   │ → _structured_score(company, role, keywords) │           │
│   └──────────────────────────────────────────────┘           │
│                                                              │
│   ┌─ LTM 向量检索 ──────────────────────────────┐           │
│   │ search_by_vector(query, user_id, top_k×2)    │           │
│   │ → pgvector 余弦搜索                          │           │
│   └──────────────────────────────────────────────┘           │
│                                                              │
│   → RRF 融合 → rerank_by_recency_importance → top-5         │
│   → 格式化 [SYSTEM MEMORY] → state["context"] + memory_hits  │
│                                                              │
│   → ★ 后续按 memory_type 分发到不同 agent（见 §4.4）         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ Session End                                                  │
│   save_memory_turn() → STM 保存本轮                          │
│   consolidate_session() → STM → LTM（异步，非阻塞）           │
│   run_periodic_maintenance() → 衰减计算 + 过期处理            │
│   end_session() → 标记会话完成                                │
└──────────────────────────────────────────────────────────────┘
```

## 3. 数据模型

### 3.1 conversation_turns 表 (STM)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | 自增 ID |
| user_id | TEXT | 用户标识 |
| session_id | TEXT FK | session 标识 |
| run_id | TEXT | 本次 run ID |
| query | TEXT | 用户输入 |
| summary_json | JSONB | 本轮 TurnSummary |
| artifacts_json | JSONB | 引用的 artifact |
| memory_tags | TEXT[] | 结构化标签 |
| created_at | TIMESTAMPTZ | 创建时间 |

索引: `(user_id, created_at DESC)`, `(session_id)`

### 3.2 conversation_sessions 表 (Session)

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | TEXT PK | 会话 ID |
| user_id | TEXT | 用户标识 |
| started_at | TIMESTAMPTZ | 开始时间 |
| ended_at | TIMESTAMPTZ | 结束时间 |
| turn_count | INTEGER | 轮次数 |
| summary | TEXT | 会话摘要 |
| key_topics | TEXT[] | 话题列表 |
| status | TEXT | active / completed / abandoned |

索引: `(user_id, status)`

### 3.3 long_term_memories 表 (LTM)

| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT PK | 记忆 ID |
| user_id | TEXT | 用户标识 |
| memory_type | TEXT | 类型（见 §3.5） |
| source_type | TEXT | 来源类型 |
| content | TEXT | 记忆文本内容 |
| structured_data | JSONB | 结构化元数据 |
| initial_importance | REAL | 初始重要性（创建时设定，不变） |
| importance | REAL | 当前重要性（时间驱动衰减计算） |
| lifetime_days | INTEGER | 生命周期（天） |
| access_count | INTEGER | 访问次数 |
| status | TEXT | active / expired_pending_refresh / soft_deleted / refresh_failed |
| content_hash | TEXT | 内容 hash（用于刷新时比较变化） |
| last_accessed_at | TIMESTAMPTZ | 最近访问时间 |
| last_refreshed_at | TIMESTAMPTZ | 最近刷新时间 |
| refresh_attempts | INTEGER | 刷新失败次数 |
| created_at | TIMESTAMPTZ | 创建时间 |
| expires_at | TIMESTAMPTZ | **硬过期时间（创建时设定）** |

### 3.4 memory_embeddings 表 (LTM pgvector)

| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT PK FK | 关联 long_term_memories |
| user_id | TEXT | 用户标识 |
| chunk_text | TEXT | 嵌入文本（截断至 2000 char） |
| source_type | TEXT | 来源类型 |
| embedding | vector(1024) | BGE-M3 嵌入向量 |
| created_at | TIMESTAMPTZ | 创建时间 |

索引: `(user_id)`, IVFFlat cosine on `embedding`

### 3.5 MemoryType 枚举（5 类）

| 类型 | 定义 | 衰减周期 | 过期行为 | 检索方式 |
|------|------|----------|----------|----------|
| **ENTITY_KNOWLEDGE** | 特定公司/岗位的可验证事实（技术栈、面试风格、薪资水平） | 180 天 | 到期刷新（stale-while-revalidate） | 公司名精确匹配 |
| **PATTERN** | 从多次行为中提取的用户特征（"后端方向，Java 栈"） | 180 天 | 到期从新行为重提取 | 始终注入 Supervisor |
| **PREFERENCE** | 用户显式或隐式表达的偏好（"只看北上广深"） | 永不过期 | 不过期 | 始终注入 |
| **SEMANTIC** | 行业通用知识、面试方法论等 | 120 天 | 到期刷新（stale-while-revalidate） | 语义向量 |
| **EPISODIC** | 单次研究的记录和结论（"Day 1 搜了字节后端，匹配度 85"） | 60 天 | 到期软删除 | 语义 + 关键词 |

类型划分依据——一个维度值得独立分类，当它在 ≥2 个轴上与其他类型有差异：

| 类型 | 衰减速度 | 检索方式 | 注入目标 | 更新频率 |
|------|----------|----------|----------|----------|
| ENTITY_KNOWLEDGE | 极慢 | 精确匹配 | SearchAgent query 扩写 | 发现新信息时 |
| PATTERN | 慢 | 始终注入 | Supervisor 路由 | 每 session 重提取 |
| PREFERENCE | 不过期 | 始终注入 | Gate 过滤 / Supervisor | 显式设置时 |
| SEMANTIC | 中 | 语义向量 | AnalysisAgent / ReportAgent | 发现新知识时 |
| EPISODIC | 快 | 语义+关键词 | MemoryRetrievalNode 上下文 | 每次运行 |

### 3.6 Memory 状态机

```
                        创建
                         │
                         ▼
                    ┌─────────┐
                    │ ACTIVE  │
                    └────┬────┘
                         │ importance ≤ 0.2 (stale 阈值)
                         ▼
              ┌──────────────────────┐
              │ EXPIRED_PENDING_     │
              │ REFRESH              │  ← 仍可检索，带"可能过时"标记
              └──────┬──────┬────────┘
                     │      │
          刷新成功   │      │ 刷新失败（对 ENTITY/SEMANTIC）
                     │      │ 或不可刷新类型（EPISODE/PATTERN）
                     │      │ importance ≤ 0.1
                     ▼      ▼
              ┌──────────┐  ┌──────────────┐
              │ ACTIVE   │  │ SOFT_DELETED │  ← 不可检索，保留记录
              │ (更新内容) │  └──────┬───────┘
              │ (重置     │         │ 30 天
              │  importance)│        ▼
              └──────────┘  ┌──────────────┐
                            │  HARD_DELETE │  ← 物理删除
                            └──────────────┘
```

- 只有 ENTITY_KNOWLEDGE 和 SEMANTIC 走刷新通道
- EPISODE 和 PATTERN 到达 stale 阈值后继续衰减，≤0.1 直接软删除
- PREFERENCE 不触发状态迁移

## 4. 记忆生命周期

### 4.1 Working Memory（当前 session）
- 存储位置：`AgentState.working_memory`（运行时上下文）
- 与 `WorkflowState.working_set` 是不同的概念：
  - `working_memory`：当前 session 内 Tool→Agent 间传递的即时上下文，不持久化，session 结束清空
  - `working_set`：WorkflowState 五层模型中的阶段中间数据层，包含 retrieval/analysis/review 子层
- Tool 层写入：SearchOrchestrator 写入检索摘要，JobAnalyzer 写入岗位快照摘要
- Agent 层读取：AnalysisAgent、ReportAgent 读取 working_memory 获取上下文

### 4.2 Session Memory 加载（Session 开始）
1. `ResearchExecutionSession.__init__()` 接受 `user_id` 参数
2. 查找或创建活跃的 ConversationSession
3. `stream_events()` 开始时调用 `load_memory_for_user(user_id)` → 加载最近一轮 TurnSummary
4. 写入 `state["memory_summary"]` 和 `state["memory_artifact_refs"]`
5. meta 事件中返回 `memory_used: true` + `conversation_summary`

### 4.3 STM 保存（Session 结束）
1. `stream_events()` 的 done event 前调用 `save_memory_turn()`
2. 从 state 中提取本轮 query + TurnSummary → 持久化到 conversation_turns
3. 更新 conversation_sessions 的 turn_count + key_topics
4. done event 中返回 `memory_used` + `conversation_summary`

### 4.4 Memory 分 Agent 注入策略（★ v2.0 新增）

替代当前 MemoryRetrievalNode 单一注入点，按 memory_type 分发到不同 agent：

```
MemoryRetrievalNode（统一检索）
    │
    ├─ ENTITY_KNOWLEDGE hits
    │   → SearchAgent: 用作 query 扩写（"字节跳动+后端+Go+系统设计"）
    │   → 不注入 prompt 文本，而是扩写搜索参数
    │
    ├─ PATTERN hits
    │   → Supervisor: 影响路由决策（用户是后端 → 预加载后端相关工具）
    │
    ├─ PREFERENCE hits
    │   → Supervisor: 影响工作流选择（只看北上广深 → 过滤地域不匹配的结果）
    │   → Gate: 质量检查时验证结果符合偏好
    │
    ├─ SEMANTIC hits
    │   → AnalysisAgent: 作为行业背景知识补充
    │   → ReportAgent: 写作时引用行业通用知识
    │
    └─ EPISODIC hits
        → MemoryRetrievalNode: 注入 [SYSTEM MEMORY] 文本块到 state["context"]
        → 所有 agent 可见（作为"上次我们做了 X"的上下文）
```

### 4.5 LTM Consolidation
在 session 结束后异步执行（`ResearchExecutionSession.stream_events()` 的 finally 块触发 `consolidate_session()`）：

1. 从当前 session 的 conversation_turns 中提取候选：
   - ENTITY_KNOWLEDGE：公司技术栈、面试风格（从 job_snapshot 提取）
   - PATTERN：用户职业方向、技术偏好（从多次匹配结果提取）
   - EPISODIC：本轮研究的 company + role + score + key_findings
2. 计算初始重要性（initial_importance）：
   - 基于 pattern 出现频率 × 一致性 × 时效
   - 公式：`importance = min(1.0, frequency_weight × 0.5 + consistency × 0.3 + recency × 0.2)`
3. 按类型设置 `lifetime_days` 和 `expires_at`：
   - expires_at = created_at + lifetime_days
4. 生成 embedding 并 upsert 到 memory_embeddings
5. 重复 upsert 策略：相同 memory_type + 相同 tag 的 LTM 记录更新 content，不新增

### 4.6 衰减机制（★ v2.0 重新设计 — 时间驱动）

**当前（v1.x）问题：** 衰减由 `apply_decay()` 调用频次驱动（每次 ×0.9），衰减速度耦合于维护频率。

**v2.0 方案：时间驱动的线性衰减**

```
importance(days) = initial_importance × max(0, 1 - days_elapsed / lifetime_days)
```

当 `days_elapsed >= lifetime_days` 时 importance 归零。

```
importance
  1.0 ┤*
      │  *
      │    *                    -- ENTITY_KNOWLEDGE (180d)
      │      *                    ·· PATTERN (180d)
      │        *                  ── SEMANTIC (120d)
  0.2 ┤ ─ ─ ─ ─ * ─ ─ ─ ─ ─    ╮ STALE 阈值
      │            *              ╯
      │              *
      │                * ─ ─ ─  ╮ SOFT_DELETE 阈值
  0.1 ┤ ─ ─ ─ ─ ─ ─ ─ ─ *      ╯
      │                      *
  0.0 ┤────────────────────────*──► days
      0        60        120     180
```

**各类型配置：**

| 类型 | lifetime_days | Stale 时间 (≤0.2) | Soft Delete 时间 (≤0.1) | 访问加固 |
|------|---------------|-------------------|------------------------|----------|
| ENTITY_KNOWLEDGE | 180 | 144 天 | 162 天 | 访问时重置 importance |
| PATTERN | 180 | 144 天 | 162 天 | 访问时重置 importance |
| PREFERENCE | ∞ | 不触发 | 不触发 | 无 |
| SEMANTIC | 120 | 96 天 | 108 天 | 访问时重置 importance |
| EPISODIC | 60 | 48 天 | 54 天 | 不加固（事件不会因访问而变新） |

访问加固：每次被检索命中 → importance = max(importance, initial_importance × (1 - days_elapsed / lifetime_days) + 0.05)。即访问暂停衰减，但不超过 initial_importance。

### 4.7 软删除与 Stale-While-Revalidate（★ v2.0 新增）

**阈值定义：**

| 阈值 | 值 | 行为 |
|------|-----|------|
| `STALE_IMPORTANCE` | 0.2 | 标记 EXPIRED_PENDING_REFRESH，触发异步刷新 |
| `SOFT_DELETE_IMPORTANCE` | 0.1 | 标记 SOFT_DELETED，不可检索 |
| `HARD_DELETE_DAYS` | 30 | 软删除后 30 天物理删除 |
| `REFRESH_MAX_RETRIES` | 3 | 刷新最大重试次数 |
| `REFRESH_FAILED_PENALTY` | 0.5 | 刷新失败后 importance 乘系数 |

**各类型的 stale 处理：**

| 类型 | ≤0.2 时的行为 | ≤0.1 时的行为 |
|------|-------------|-------------|
| ENTITY_KNOWLEDGE | 用 company+source_type 重新搜索 Web → 对比 content_hash → 更新或重置 | 刷新失败 ×3 → SOFT_DELETED |
| PATTERN | 从最近 turns 重新提取 pattern → 更新或重置 | 重提取失败 ×3 → SOFT_DELETED |
| PREFERENCE | 不触发 | 不触发 |
| SEMANTIC | 同 ENTITY_KNOWLEDGE，重新搜索验证 | 刷新失败 ×3 → SOFT_DELETED |
| EPISODIC | 不做刷新，继续衰减 | 直接 SOFT_DELETED |

**刷新成功判定：**
- Web 搜索返回新内容且与旧 content_hash 差异 >30% → 更新 content、重置 importance、重置 expires_at
- 内容一致 → 仅更新 `last_refreshed_at`、重置 importance、重置 expires_at

## 5. RAG ↔ Memory 桥接

在 `auto_writeback()` 成功后触发：

```python
if quality_score >= 80 and freshness_score >= 70:
    await ltm_store.save(LongTermMemory(
        memory_type=MemoryType.ENTITY_KNOWLEDGE,
        content=f"{company} {source_type}: {snippet}",
        importance=0.7,
        lifetime_days=180,
        expires_at=utc_now() + timedelta(days=180),
    ))
```

搜索越多 → RAG 缓存越丰富 → LTM 同步积累公司知识 → 后续搜索更高效。

## 6. user_id 来源
- API 请求显式传入 `user_id`
- 如果 `user_id` 为空，不启用记忆功能
- 不引入登录认证，不从 `candidate_profile.candidate_id` 隐式推导

## 7. 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ENABLE_CONVERSATION_MEMORY` | `True` | 是否启用 STM 对话记忆 |
| `ENABLE_LTM` | `True` | 是否启用 LTM 长期记忆 |
| `MEMORY_BACKEND` | `postgresql` | 存储后端（SQLite 分支已移除） |
| `LTM_DATABASE_URL` | (必需) | PostgreSQL 连接串 |
| `STALE_IMPORTANCE` | `0.2` | 触发刷新/标记过期的 importance 阈值 |
| `SOFT_DELETE_IMPORTANCE` | `0.1` | 软删除的 importance 阈值 |
| `HARD_DELETE_DAYS` | `30` | 软删除后多少天物理删除 |
| `REFRESH_MAX_RETRIES` | `3` | 刷新最大重试次数 |
| `REFRESH_FAILED_PENALTY` | `0.5` | 刷新失败后 importance 乘系数 |

## 8. 关键约束
- 记忆只存储 summary 和 artifact refs，不存储完整 state
- 记忆 summary 可以写入 workflow state 供后续节点按需裁剪使用
- 不把完整历史消息无差别注入 LLM prompt
- 记忆加载/保存失败不阻断主流程，静默降级
- 记忆按 user 维度隔离，不支持跨 user 查询
- LTM consolidation 异步执行，不阻塞 session
- SOFT_DELETED 状态不可检索，但保留记录用于分析
- PostgreSQL 为必需依赖，SQLite 分支已移除，消除双后端维护成本
- expires_at 在创建时明确设定，不依赖外部定时任务

## 9. 实现文件
- `api/core/conversation_memory.py` — 向后兼容 facade
- `api/core/memory/models.py` — STM/LTM 数据模型（含 MemoryType 枚举和 MemoryStatus 状态机）
- `api/core/memory/stm_store.py` — STM 存储层（仅 PostgreSQL）
- `api/core/memory/ltm_store.py` — LTM 存储层（pgvector + 时间衰减函数 + 软删除逻辑）
- `api/core/memory/consolidation.py` — consolidation 逻辑 + 周期性维护
- `api/core/memory/retrieval.py` — 记忆检索（STM + LTM 混合查询 + RRF 融合）
- `api/core/memory/refresh.py` — stale-while-revalidate 刷新逻辑（新增）
- `api/agents/memory_retrieval.py` — MemoryRetrievalNode + 分发注入
- `api/core/executor.py` — Session 集成
- `api/main.py` — 接收 `user_id` 并传给 session
- `api/core/settings.py` — 所有 Memory 相关配置

## 10. 实现状态
- **已完成**: STM 存储层、Session 集成（加载/保存）、显式 user_id、LTM 存储与检索、RRF 混合检索、consolidation 流程、衰减机制（v1.x 调用频次驱动）
- **规划中（Module C）**: MemoryType 5 类重分类、时间驱动衰减（v2.0）、软删除 + stale-while-revalidate、分 agent 注入策略、RAG ↔ Memory 桥接、PostgreSQL 统一后端、SQLite 分支移除
