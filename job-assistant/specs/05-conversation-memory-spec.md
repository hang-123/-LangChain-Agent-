# 对话记忆规范（阶段二）

## 1. 目标
为 Job Assistant 提供完整的跨 session 记忆系统，包含三层架构：

1. **Working Memory** — 当前 session 的即时上下文（AgentState，不持久化）
2. **Short-Term Memory (STM)** — 同一 session 内多轮对话，按 user_id 隔离
3. **Long-Term Memory (LTM)** — 跨 session 持久记忆，带向量检索和衰减

## 2. 三层架构

```
┌─────────────────────────────────────────────┐
│              WORKING MEMORY                  │
│  AgentState.working_memory                   │
│  当前 session 的即时上下文，不持久化           │
│  节点可读写，session 结束清空                  │
└─────────────────────┬───────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   Session 结束       │
           │   save_memory_turn() │
           ▼                     ▼
┌──────────────────┐    ┌──────────────────┐
│   STM (SQLite/   │    │   LTM (pgvector) │
│    PostgreSQL)   │    │                  │
│                  │    │  跨 session 持久  │
│  同 session 内    │    │  语义检索 + 衰减  │
│  多轮对话         │───▶│  consolidation   │
│  按 user_id 隔离  │    │  重要性评分       │
└──────────────────┘    └──────────────────┘
```

- 工作记忆：Tool 间的短期上下文传递
- STM：当前 session 的完整轮次记录
- LTM：跨 session 的 pattern 和偏好，consolidation 从 STM 升级

## 3. 数据模型

### conversations 表 (STM)
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | TEXT PK | 用户标识 |
| conversation_id | TEXT | 会话 ID（`conv::{user_id}`） |
| summary | TEXT | 最新一轮的摘要 |
| artifact_refs | JSONB | 引用 artifact ID |
| updated_at | TIMESTAMPTZ | 更新时间 |

### conversation_turns 表 (STM)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | 自增 ID |
| user_id | TEXT FK | 用户标识 |
| session_id | TEXT | session 标识 |
| run_id | TEXT | 本次 run ID |
| query | TEXT | 用户输入 |
| summary | TEXT | 本轮摘要 |
| artifact_refs | JSONB | 引用的 artifact |
| created_at | TIMESTAMPTZ | 创建时间 |

### long_term_memories 表 (LTM, 阶段二新增)
| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT PK | 记忆 ID |
| user_id | TEXT | 用户标识 |
| memory_type | TEXT | 类型: match_pattern / skill_gap / preference / feedback |
| content | TEXT | 记忆内容 |
| embedding | vector(1536) | 语义向量 |
| source_turns | JSONB | 来源 turn ID 列表 |
| importance | REAL | 重要性评分 0-1 |
| decay_factor | REAL | 衰减因子 |
| created_at | TIMESTAMPTZ | 创建时间 |
| last_accessed_at | TIMESTAMPTZ | 最近访问时间 |

### memory_tags 表 (LTM, 阶段二新增)
| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT FK | 关联记忆 |
| tag | TEXT | 标签（公司名、岗位名等） |

## 4. 记忆生命周期

### 4.1 Working Memory（当前 session）
- 存储位置：`AgentState.working_memory`（运行时上下文，与 WorkflowState 的 `working_set` 是不同的概念）
  - `working_memory`：当前 session 内 Tool→Agent 间传递的即时上下文，不持久化，session 结束清空
  - `working_set`：WorkflowState 五层模型中的阶段中间数据层，包含 retrieval/analysis/review 子层，持久化在 state 中
- Tool 层写入：SearchOrchestrator 写入检索摘要，JobAnalyzer 写入岗位快照摘要
- Agent 层读取：AnalysisAgent、ReportAgent 读取 working_memory 获取上下文
- Session 结束时清空

### 4.2 STM 加载（Session 开始）
与 LTM 检索在同一 `memory_retrieval_node` 中同步完成：
1. `ResearchExecutionSession.__init__()` 接受 `user_id` 参数
2. 如果 `ENABLE_CONVERSATION_MEMORY=1` 且 `user_id` 非空，创建 `memory_store`
3. `stream_events()` 开始时调用 `load_memory_for_user(user_id)` → 加载 STM 历史摘要
4. 同时调用 LTM 语义检索 → 召回相关长期记忆
5. 如果有历史记录，写入 `state["memory_summary"]` 和 `state["memory_artifact_refs"]`
6. meta 事件中返回 `memory_used: true` + `conversation_summary`

### 4.3 STM 保存（Session 结束）
1. `stream_events()` 的 done event 前调用 `save_memory_turn()`
2. `build_turn_summary()` 从 state 中提取本轮 query + artifact refs
3. 持久化到 conversations（upsert）和 conversation_turns（insert）
4. done event 中返回 `memory_used` + `conversation_summary`

### 4.4 LTM Consolidation（阶段二新增）
在 session 结束后异步执行（由 `ResearchExecutionSession.stream_events()` 的 finally 块触发 `consolidate_session()`）：

1. 从当前 session 的 conversation_turns 中提取候选 pattern：
   - 匹配 pattern（"用户对后端实习推荐度通常是 recommended_with_risks"）
   - 技能差距 pattern（"用户连续多轮缺少分布式系统经验证据"）
   - 用户偏好（"用户偏好上海、杭州的岗位"）
   - 反馈 pattern
2. 从 RAG 命中结果中提取高质量记录（quality_score >= 80 且 freshness_score >= 70）：
   - 关联 pattern：记录"用户检索过 X 公司 Y 岗位，命中 Z 资料"
   - 作为技能差距和匹配模式的补充信号
3. 计算重要性评分（importance）：
   - 基于 pattern 出现频率 × 一致性 × 时效
   - 公式：`importance = min(1.0, frequency_weight × 0.5 + consistency × 0.3 + recency × 0.2)`
   - frequency_weight = min(1.0, 命中次数 / 3)
   - consistency = 1.0（所有 turns 结论一致）递减到 0.3（结论矛盾）
   - recency = 1.0（最近 1 天内）递减到 0.1（超过 MEMORY_DECAY_DAYS 天）
4. 生成 embedding 并 upsert 到 `long_term_memories` 表
5. 为新记忆生成标签（公司名、岗位名、技能名）
6. 重复 upsert 策略：相同 memory_type + 相同标签的 LTM 记录更新 importance 和 content，不新增记录

### 4.5 LTM 检索（Session 中，阶段二新增）
在 `memory_retrieval_node` 中（位于 Supervisor 之后、SearchOrchestrator 之前执行）：
1. 用当前 query + query_profile 做语义检索 → 召回 top-k LTM 命中
2. 按 `importance × decay_factor` 排序
3. 高于阈值的命中写入 `state["memory_hits"]`
4. 下游 Agent 可通过 memory_hits 获取历史背景

### 4.6 衰减机制（阶段二新增）
- `decay_factor` 初始值为 1.0
- 每次被检索命中 → decay_factor = min(1.0, decay_factor + 0.05)（巩固）
- 每经过 `MEMORY_DECAY_DAYS` 天未被访问 → decay_factor = max(0.1, decay_factor × 0.85)
- decay_factor < 0.3 → 标记为"冷记忆"，不注入 prompt

## 5. user_id 来源
- API 请求显式传入 `user_id`
- 如果 `user_id` 为空，不启用记忆功能
- 不引入登录认证，不从 `candidate_profile.candidate_id` 隐式推导

## 6. 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ENABLE_CONVERSATION_MEMORY` | `0` | 是否启用 STM 对话记忆 |
| `ENABLE_LTM` | `0` | 是否启用 LTM 长期记忆 |
| `MEMORY_BACKEND` | `auto` | 存储后端：auto / sqlite / postgresql |
| `MEMORY_DECAY_DAYS` | `30` | LTM 衰减周期 |
| `RAG_DATABASE_URL` | (空) | PostgreSQL 连接串（共享 RAG 的 PG 实例） |

## 7. 关键约束
- 记忆只存储 summary 和 artifact refs，不存储完整 state
- 记忆 summary 可以写入 workflow state 供后续节点按需裁剪使用
- 不把完整历史消息无差别注入 LLM prompt
- 记忆加载/保存失败不阻断主流程，静默降级
- 记忆按 user 维度隔离，不支持跨 user 查询
- LTM consolidation 异步执行，不阻塞 session
- 冷记忆（decay_factor < 0.3）不注入 prompt，但保留在数据库中

## 8. 实现文件
- `api/core/conversation_memory.py` — 向后兼容 facade
- `api/core/memory/models.py` — STM/LTM 数据模型
- `api/core/memory/stm_store.py` — STM 存储层（SQLite / PostgreSQL）
- `api/core/memory/ltm_store.py` — LTM 存储层（pgvector）
- `api/core/memory/consolidation.py` — consolidation 逻辑
- `api/core/memory/retrieval.py` — 记忆检索（STM + LTM 联合查询）
- `api/agents/memory_retrieval.py` — MemoryRetrievalNode
- `api/core/executor.py` — Session 集成
- `api/main.py` — 接收 `user_id` 并传给 session
- `api/core/settings.py` — ENABLE_CONVERSATION_MEMORY, ENABLE_LTM 等配置

## 9. 实现状态
**阶段一已完成**: STM 存储层、Session 集成（加载/保存）、显式 user_id、done event / API 输出、向后兼容 facade。
**阶段二目标**: Working Memory 工具间传递、LTM 存储与检索、consolidation 流程、衰减机制、MemoryRetrievalNode 完整集成。
