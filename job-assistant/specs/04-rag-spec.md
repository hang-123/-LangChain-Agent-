# RAG 集成规范（阶段二）

## 1. 目标
为 SearchOrchestrator 提供基于 pgvector 的历史岗位文档检索能力。阶段二在阶段一基础上新增：
- 搜索后自动回写高质量结果到 pgvector
- RAG 结果的时效性权重调整
- LTM 集成：将高价值 RAG 命中关联到用户长期记忆

## 2. 架构

```
Tavily 工具并发检索 → RAG 检索 (pgvector) → URL 去重合并 → _select_sources → evidence_items
                                                         ↓
                                                    auto_writeback (可选)
                                                    高质量结果 upsert 回 pgvector
```

- RAG 结果作为**补充源**，不替代 Tavily
- RAG 失败不阻断搜索流程
- 搜索完成后，高质量结果自动回写 pgvector（ENABLE_RAG_WRITEBACK=1 时）

## 3. 数据流

### 3.1 RAG 入库（离线 + 在线）
- `JobDocument` → `chunk_job_document()` → 逐 chunk 计算 embedding → 写入 `job_chunks` 表
- 支持增量 upsert（`ON CONFLICT(document_id) DO UPDATE`）
- **阶段二新增**：`auto_writeback()` 在每次搜索结束后，将 quality_score >= 70 的 Tavily 结果自动入库

### 3.2 RAG 检索（在线）
- `search_orchestrator_node()` 在工具结果返回后调用 `search_rag_sources()`
- 传入当前 query + query_profile，返回 top-k 个 `RagSearchHit`
- 命中结果转为 `NormalizedSource`，合并进 `ToolSearchResult(tool_name="rag_vector_search")`
- 统一走 `_select_sources()` 的评分、去重、截断逻辑

### 3.3 时效性权重调整（阶段二新增）
RAG 结果在 `_select_sources()` 中按时效衰减。freshness_score 计算公式：
- `freshness_score = max(0, 100 - days_since_ingestion × 2)`（每天衰减2分，50天后归零）
- 结果分档：
  - `freshness_score >= 80`：原始 quality_score
  - `freshness_score 60-79`：quality_score × 0.85
  - `freshness_score 40-59`：quality_score × 0.7
  - `freshness_score < 40`：quality_score × 0.5，且标记 `may_be_stale`

### 3.4 LTM 关联（阶段二新增）
RAG 命中中 `quality_score >= 80` 且 `freshness_score >= 70` 的结果，可被 consolidation 流程关联到用户 LTM：记录"用户检索过 X 公司 Y 岗位，命中 Z 资料"的 pattern。

## 4. 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ENABLE_RAG` | `0` | 是否启用 RAG |
| `ENABLE_RAG_WRITEBACK` | `0` | 是否自动回写搜索结果 |
| `RAG_WRITEBACK_QUALITY_THRESHOLD` | `70` | 回写的质量分阈值 |
| `RAG_DATABASE_URL` | (空) | pgvector 连接串 |
| `RAG_TOP_K` | `4` | 每次检索返回的 top-k |
| `EMBEDDING_DIM` | `1536` | embedding 维度 |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | embedding 模型 |

## 5. 关键约束
- `ALLOWED_SOURCE_TYPES = {"jd", "company_profile", "interview", "tech_stack", "salary_culture"}` — 只允许这5类岗位资料进入 RAG
- RAG 检索失败时，将错误信息写入 `rag_failures`，不抛异常
- RAG 命中结果的 URL 去重基于 `existing_urls` 集合
- RAG 结果不参与缓存（缓存 key 只基于 query + intent + profile）
- RAG 资料只作为岗位侧 evidence，不写入 `CandidateProfile` 或 `ResumeEvidence`
- 自动回写时跳过 `source_type` 不在 `ALLOWED_SOURCE_TYPES` 中的结果
- 自动回写需先检查是否与已有 document 重复（URL 去重），已存在的只更新 `updated_at`

## 6. 实现文件
- `api/core/rag_store.py` — RagStore、chunk_job_document、search_rag_sources、safe_search_rag、auto_writeback（新增）
- `api/agents/search_agent.py` — search_agent_node() 中集成 RAG 调用（迁移为 SearchOrchestrator）
- `api/core/settings.py` — 新增 ENABLE_RAG_WRITEBACK、RAG_WRITEBACK_QUALITY_THRESHOLD 等配置
- `api/core/memory/ltm_store.py` — RAG 命中与 LTM 的关联逻辑

## 7. 实现状态
**阶段一已完成**: RAG 存储层、检索层、SearchAgent 集成、诊断输出。
**阶段二目标**: 自动回写、时效权重调整、LTM 关联。
