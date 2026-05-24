# RAG 集成规范

> 最后更新: 2026-05-18 | 版本: v2.0

## 1. 目标
为 SearchOrchestrator 提供基于 pgvector 的历史岗位文档检索能力，包括：
- 搜索后自动回写高质量结果到 pgvector
- RAG 结果的时效性权重调整
- Dense + Sparse 混合检索，兼顾语义相似度和词法精确匹配
- LTM 集成：将高价值 RAG 命中关联到用户长期记忆

## 2. 架构

```
Tavily 工具并发检索 → RAG 检索 (pgvector) → URL 去重合并 → _select_sources 统一打分
                         │                                      │
                         │  Dense (向量余弦)                     │
                         │  + Sparse (词法 BM25)                │
                         │  → RRF 融合                          │
                         │                                      │
                         └──────────────────────────────────────┤
                                                    auto_writeback (默认开启)
                                                    高质量结果 upsert 回 pgvector
```

- RAG 结果作为**补充源**，不替代 Tavily
- RAG 失败不阻断搜索流程
- 搜索完成后，高质量结果自动回写 pgvector
- RAG 缓存的可信度高于首次 Tavily 抓取（已验证内容 > 未验证内容）

## 3. 数据流

### 3.1 RAG 入库（离线 + 在线）
- `JobDocument` → `chunk_job_document()` → 逐 chunk 计算 embedding → 写入 `job_chunks` 表
- 支持增量 upsert（`ON CONFLICT(document_id) DO UPDATE`）
- `auto_writeback()` 在每次搜索结束后，将 quality_score >= 70 的 Tavily 结果自动入库

### 3.2 分块策略（按 source_type 差异化）

不再使用统一 900 字符固定分块。按文档类型选择分块策略：

| source_type | 策略 | chunk_size | overlap | 说明 |
|-------------|------|------------|---------|------|
| `jd` | 按 Markdown 标题切分（`##`/`###`） | — | 0 | JD 有天然章节结构 |
| `company_profile` | 按 Markdown 标题切分（`##`） | — | 0 | 公司介绍按板块切 |
| `interview` | Q&A 对切分 + 单对 max 800 字符 | 800 | 0 | 面经 Q&A 是自然单位 |
| `tech_stack` | 句子级切分 | 600 | 200 | 技术栈短，加 overlap 保完整性 |
| `salary_culture` | 句子级切分 | 600 | 200 | 同 tech_stack |

### 3.3 RAG 检索（在线）— Dense + Sparse 混合

**嵌入模型：BGE-M3（云端调用）**
- 首选：硅基流动 SiliconFlow BGE-M3（1024d）
- 备选：阿里云 DashScope text-embedding-v4（1024d，原生支持 dense+sparse 双输出）
- 本地开发备选：BGE-M3 本地部署
- 嵌入层抽象出 `EmbeddingBackend` 接口，支持后端切换

**检索流程：**
```
query + profile
    │
    ├─→ Dense 分支: embedding → pgvector cosine search
    │
    ├─→ Sparse 分支: PostgreSQL tsvector 关键词匹配 (company/role/tech keywords)
    │       ts_rank(to_tsvector('simple', text), plainto_tsquery('simple', keywords))
    │
    └─→ RRF 融合 (k=60)
        │
        排序 → top-k → NormalizedSource 列表
```

- Dense 权重 0.7，Sparse 权重 0.3（可在 settings 中配置）
- Sparse 确保精确命中公司名、技术栈名等短词
- 如果 BGE-M3 可用其原生 sparse vectors，替代 PostgreSQL tsvector

### 3.4 与 Tavily 的合并策略

```
RAG hits                        Tavily results
    │                                │
    ├─ URL 去重:                      │
    │   同一 URL → Tavily 优先 (最新)  │
    │   RAG 独有 URL → 保留           │
    │                                │
    ├─ 包装为 ToolSearchResult        │
    │   tool_name="rag_vector_search" │
    │                                │
    └──────── _select_sources() 统一打分 ─────┘
                    │
              RAG 来源 +0.5 可信度加权（已验证内容）
                    │
              时效衰减 → selected (最多 12 条)
```

- RAG 和 Tavily 不设固定比例，完全由打分决定
- RAG 命中打 `+0.5` 可信度加分（因是历史验证过的高质量结果）
- RAG 结果也不参与缓存（缓存 key 只基于 query + intent + profile）

### 3.5 时效性权重调整
所有来源（Tavily + RAG）统一应用时效衰减：

- `freshness_score = max(0, 100 - days_since_ingestion × 2)`（每天衰减 2 分，50 天后归零）
- 结果分档：
  - `freshness_score >= 80`：原始 quality_score
  - `freshness_score 60-79`：quality_score × 0.85
  - `freshness_score 40-59`：quality_score × 0.7
  - `freshness_score < 40`：quality_score × 0.5，且标记 `may_be_stale`

### 3.6 Reranker 接口预留

当前不引入 cross-encoder reranker（避免增加延迟和成本），但预留接口：

```python
class RerankerBackend(Protocol):
    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        """Rerank documents given a query, returning (doc_index, score) pairs."""
        ...

# 后续可接入:
# - BGE-Reranker-v2-m3 (本地)
# - Cohere Rerank v3 (云端)
# 当前实现: NullReranker (passthrough)
```

### 3.7 LTM 关联（RAG ↔ Memory 桥接）

RAG 命中中 `quality_score >= 80` 且 `freshness_score >= 70` 的结果，自动写入 LTM：

```python
# auto_writeback 成功后:
if quality_score >= 80 and freshness_score >= 70:
    await ltm_store.save(LongTermMemory(
        memory_type=MemoryType.ENTITY_KNOWLEDGE,
        content=f"{company} {source_type}: {snippet}",
        source_type=source_type,
        importance=0.7,
        expires_at=created_at + timedelta(days=180),  # 半年
    ))
```

这建立了 RAG 缓存 → LTM 的正向循环：搜索越多 → 缓存越丰富 → 记忆越准确 → 后续搜索越高效。

## 4. 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ENABLE_RAG` | `True` | 是否启用 RAG |
| `ENABLE_RAG_WRITEBACK` | `True` | 是否自动回写搜索结果 |
| `RAG_WRITEBACK_QUALITY_THRESHOLD` | `70` | 回写的质量分阈值 |
| `RAG_DATABASE_URL` | (必需) | pgvector 连接串 |
| `RAG_TOP_K` | `4` | 每次检索返回的 top-k |
| `EMBEDDING_DIM` | `1024` | embedding 维度（BGE-M3） |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | embedding 模型名称 |
| `EMBEDDING_PROVIDER` | `siliconflow` | 嵌入提供方: siliconflow / dashscope / local |
| `RAG_DENSE_WEIGHT` | `0.7` | Dense 向量权重 |
| `RAG_SPARSE_WEIGHT` | `0.3` | Sparse 词法权重 |
| `RAG_TRUST_BONUS` | `0.5` | RAG 已验证内容的可信度加分 |
| `ENABLE_RERANKER` | `False` | 是否启用 reranker（预留） |

## 5. 关键约束
- `ALLOWED_SOURCE_TYPES = {"jd", "company_profile", "interview", "tech_stack", "salary_culture"}` — 只允许这 5 类岗位资料进入 RAG
- RAG 检索失败时，将错误信息写入 `rag_failures`，不抛异常
- RAG 命中结果的 URL 去重基于 `existing_urls` 集合
- RAG 结果不参与缓存（缓存 key 只基于 query + intent + profile）
- RAG 资料只作为岗位侧 evidence，不写入 `CandidateProfile` 或 `ResumeEvidence`
- 自动回写时跳过 `source_type` 不在 `ALLOWED_SOURCE_TYPES` 中的结果
- 自动回写需先检查是否与已有 document 重复（URL 去重），已存在的只更新 `updated_at`
- PostgreSQL + pgvector 为必需依赖，不再有 SQLite fallback
- 嵌入模型通过 `EmbeddingBackend` 接口抽象，支持 provider 切换

## 6. 实现文件
- `api/core/rag_store.py` — RagStore、分块策略、search_rag_sources、safe_search_rag、auto_writeback
- `api/core/embedding.py` — EmbeddingBackend 接口 + BGE-M3 / OpenAI 实现（新增）
- `api/agents/search_agent.py` — search_agent_node() 中 RAG 集成、可信度加权、混合检索
- `api/core/settings.py` — 嵌入模型、reranker、混合检索权重等配置
- `api/core/memory/ltm_store.py` — RAG ↔ LTM 桥接

## 7. 实现状态
- **已完成**: RAG 存储层（pgvector）、检索层（纯向量）、SearchAgent 集成、自动回写、时效衰减
- **规划中**: BGE-M3 切换 + EmbeddingBackend 抽象、按 source_type 分块策略、Dense+Sparse 混合检索、Reranker 接口、RAG 可信度加权、RAG ↔ LTM 桥接
