# Phase 4: Memory & RAG Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the context duplication bug, wire up LTM pgvector semantic search, and implement spec 04 RAG freshness decay — closing the 3 remaining quality gaps in memory and search.

**Architecture:** Context fix is a 2-line change in each of 2 files (return only new items, not accumulated list). LTM pgvector search reuses the existing `embed_query` from `rag_store.py` and the pgvector connection pattern to add a `memory_embeddings` table and a `vector_search_fn` callback wired through `memory_retrieval_node`. RAG freshness decay replaces the year-based `_freshness_score()` with the spec's day-based `max(0, 100 - days × 2)` formula.

**Tech Stack:** Python async, pgvector/psycopg, SQLite (aiosqlite), existing `api/core/llm.embed_query`, pytest

---

## File Structure

### Create
- (none)

### Modify
- `api/agents/analysis_agent.py` — Fix context duplication: return only new items
- `api/agents/memory_retrieval.py` — Fix context duplication: return only new items; wire `vector_search_fn`
- `api/core/memory/ltm_store.py` — Add pgvector-backed `search_by_vector()` method to `SqliteLongTermMemoryStore`
- `api/core/memory/retrieval.py` — No changes needed (already accepts `vector_search_fn`)
- `api/agents/search_agent.py` — Replace `_freshness_score()` with spec day-based decay; add freshness multiplier in `_select_sources()`
- `api/core/rag_store.py` — Add `updated_at` to `RagSearchHit`; add freshness decay in `search()` results
- `api/core/settings.py` — Add `ltm_database_url` setting for pgvector connection

---

### Task 1: Fix Context Duplication Bug

**Files:**
- Modify: `api/agents/analysis_agent.py:295-304`
- Modify: `api/agents/memory_retrieval.py:74-81`

The `context` field in `AgentState` uses `Annotated[List[str], operator.add]` as its reducer. This means LangGraph concatenates the returned list with the existing list. When nodes return the full accumulated list (existing + new), every item gets duplicated.

- [ ] **Step 1: Read current code in both files**

Open `api/agents/memory_retrieval.py` and `api/agents/analysis_agent.py` to see the current `context` handling.

- [ ] **Step 2: Fix memory_retrieval.py**

In `api/agents/memory_retrieval.py`, change lines 74-81 from returning the full list to returning only new context items:

```python
    # BEFORE (buggy — returns full list causing duplication):
    context = list(state.get("context") or [])
    if memory_context.formatted_text:
        context.append(memory_context.formatted_text)

    return {
        "working_memory": working_memory,
        "memory_hits": memory_hits,
        "context": context,  # BUG: full list + operator.add = duplication
    }

    # AFTER (fixed — returns only new items):
    new_context: list[str] = []
    if memory_context.formatted_text:
        new_context.append(memory_context.formatted_text)

    return {
        "working_memory": working_memory,
        "memory_hits": memory_hits,
        "context": new_context,  # FIXED: only new items, operator.add appends them
    }
```

- [ ] **Step 3: Fix analysis_agent.py**

In `api/agents/analysis_agent.py`, change lines 187-222 and 295-304. The function loads existing context, appends `tool_context_summary`, then returns the full list. Fix by tracking only new items:

```python
    # BEFORE (buggy — line 187):
    context = list(state.get("context") or [])

    # ... later appends tool_context_summary to context (line 222) ...

    # BEFORE (buggy — line 295-296):
    return {
        "context": context,  # BUG: full accumulated list
        ...
    }

    # AFTER (fixed):
    new_context: list[str] = []

    # ... when tool_context_parts is non-empty (line 220-222), change from:
    #   context.append(tool_context_summary)
    # to:
    #   new_context.append(tool_context_summary)

    return {
        "context": new_context,  # FIXED: only new items
        ...
    }
```

The exact change in analysis_agent.py:

**Line 187:** Remove `context = list(state.get("context") or [])`

**Lines 198-222:** Replace:
```python
    # Phase 2: read working_memory from upstream tools for enriched context
    working_memory = list(state.get("working_memory") or [])
    tool_context_parts: list[str] = []
    for entry in working_memory:
        ...
    if tool_context_parts:
        tool_context_summary = "上游工具摘要：\n" + "\n".join(f"- {p}" for p in tool_context_parts)
        context.append(tool_context_summary)
```

With:
```python
    # Phase 2: read working_memory from upstream tools for enriched context
    new_context: list[str] = []
    working_memory = list(state.get("working_memory") or [])
    tool_context_parts: list[str] = []
    for entry in working_memory:
        ...
    if tool_context_parts:
        tool_context_summary = "上游工具摘要：\n" + "\n".join(f"- {p}" for p in tool_context_parts)
        new_context.append(tool_context_summary)
```

**Line 295-296:** Replace `"context": context,` with `"context": new_context,`

- [ ] **Step 4: Run existing tests to verify no regression**

Run: `python -m pytest tests/test_phase2_connectivity.py tests/test_search_agent_cache.py tests/test_search_agent_rag.py tests/test_job_analyzer.py tests/test_matching_engine.py tests/test_gate.py -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add api/agents/memory_retrieval.py api/agents/analysis_agent.py
git commit -m "fix: return only new context items to prevent operator.add duplication"
```

---

### Task 2: Add LTM pgvector Search Capability

**Files:**
- Modify: `api/core/memory/ltm_store.py` — Add pgvector table initialization and `search_by_vector()` method
- Modify: `api/core/settings.py` — Add `ltm_database_url` setting
- Modify: `api/agents/memory_retrieval.py` — Wire `vector_search_fn` to `retrieve_memories()`

- [ ] **Step 1: Add `ltm_database_url` setting**

In `api/core/settings.py`, find the existing memory/RAG settings and add:

```python
    # LTM pgvector
    ltm_database_url: str = ""
```

With env var alias `LTM_DATABASE_URL`.

- [ ] **Step 2: Add pgvector table and search method to SqliteLongTermMemoryStore**

In `api/core/memory/ltm_store.py`, add a new method `_ensure_pgvector_table()` and `search_by_vector()`.

First, add imports at the top after existing imports:

```python
try:
    import psycopg
    from pgvector.psycopg import register_vector
except Exception:
    psycopg = None  # type: ignore
    register_vector = None  # type: ignore
```

Then add methods to `SqliteLongTermMemoryStore`:

```python
    def _pg_connect(self):
        """Connect to pgvector for LTM semantic search."""
        from api.core.settings import get_settings
        settings = get_settings()
        url = str(settings.ltm_database_url or "").strip()
        if not url or psycopg is None:
            return None
        conn = psycopg.connect(url)
        if register_vector is not None:
            register_vector(conn)
        return conn

    def _ensure_pgvector_table(self) -> bool:
        """Create pgvector memory_embeddings table if not exists. Returns True if available."""
        conn = self._pg_connect()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_embeddings (
                        memory_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        chunk_text TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        embedding vector(1536) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_embeddings_user "
                    "ON memory_embeddings(user_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_embeddings_vector "
                    "ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)"
                )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    async def search_by_vector(
        self, query: str, user_id: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Vector semantic search over memory embeddings using pgvector.
        
        Args:
            query: Natural language search query.
            user_id: User identifier.
            top_k: Number of results to return.
            
        Returns:
            List of dicts with {memory_id, user_id, chunk_text, source_type, score}.
        """
        from api.core.llm import embed_query
        
        conn = self._pg_connect()
        if conn is None:
            return []
        
        try:
            embedding = await embed_query(query)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT memory_id, user_id, chunk_text, source_type,
                           1 - (embedding <=> %s::vector) AS score
                    FROM memory_embeddings
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, user_id, embedding, int(top_k)),
                )
                rows = cur.fetchall()
            return [
                {
                    "memory_id": row[0],
                    "user_id": row[1],
                    "chunk_text": row[2],
                    "source_type": row[3],
                    "score": float(row[4] or 0.0),
                }
                for row in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()

    async def upsert_memory_embedding(
        self, memory_id: str, user_id: str, chunk_text: str, source_type: str
    ) -> bool:
        """Store a memory embedding in pgvector for later semantic search."""
        from api.core.llm import embed_query
        
        conn = self._pg_connect()
        if conn is None:
            return False
        
        if not self._ensure_pgvector_table():
            return False
        
        try:
            embedding = await embed_query(chunk_text)
            conn2 = self._pg_connect()
            if conn2 is None:
                return False
            try:
                with conn2.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO memory_embeddings (memory_id, user_id, chunk_text, source_type, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (memory_id) DO UPDATE SET
                            chunk_text = excluded.chunk_text,
                            embedding = excluded.embedding
                        """,
                        (memory_id, user_id, chunk_text, source_type, embedding),
                    )
                conn2.commit()
                return True
            finally:
                conn2.close()
        except Exception:
            return False
```

- [ ] **Step 3: Build vector_search_fn adapter for retrieve_memories**

In `api/agents/memory_retrieval.py`, build a `vector_search_fn` that wraps `ltm_store.search_by_vector()` and returns `list[MemoryHit]`:

Add after `ltm_store = build_ltm_store()`:

```python
    # Build vector_search_fn if pgvector is available
    vector_search_fn = None
    if ltm_store is not None and hasattr(ltm_store, 'search_by_vector'):
        async def _vector_search(q: str, uid: str, k: int) -> list:
            from api.core.memory.models import LongTermMemory, MemoryHit, MemoryType, SourceType
            rows = await ltm_store.search_by_vector(q, uid, k)
            hits: list = []
            for row in rows:
                mem = LongTermMemory(
                    memory_id=row["memory_id"],
                    user_id=row["user_id"],
                    memory_type=MemoryType.SEMANTIC,
                    source_type=SourceType(row.get("source_type", "evaluation_report")),
                    content=row["chunk_text"],
                    importance=0.5,
                )
                hits.append(MemoryHit(
                    memory=mem,
                    score=row["score"],
                    retrieval_method="vector",
                ))
            return hits
        vector_search_fn = _vector_search
```

Then pass it to `retrieve_memories()`:

```python
    memory_context = await retrieve_memories(
        ltm_store=ltm_store,
        stm_store=stm_store,
        query=query,
        query_profile=query_profile,
        user_id=user_id,
        top_k=5,
        vector_search_fn=vector_search_fn,  # NEW: wire pgvector search
    )
```

- [ ] **Step 4: Store embeddings when saving LTM memories**

In `SqliteLongTermMemoryStore.save()`, after the INSERT, add a call to upsert the embedding:

```python
    async def save(self, memory: LongTermMemory) -> str:
        # ... existing INSERT logic ...
        
        # Try to store embedding for vector search
        if memory.content.strip():
            await self.upsert_memory_embedding(
                memory_id=memory_id,
                user_id=memory.user_id,
                chunk_text=memory.content[:2000],  # Truncate long content
                source_type=memory.source_type.value,
            )
        
        return memory_id
```

- [ ] **Step 5: Run memory tests**

Run: `python -m pytest tests/test_memory_system.py tests/test_conversation_memory.py -v`
Expected: All existing memory tests pass

- [ ] **Step 6: Commit**

```bash
git add api/core/memory/ltm_store.py api/core/settings.py api/agents/memory_retrieval.py
git commit -m "feat: wire LTM pgvector semantic search with vector_search_fn callback"
```

---

### Task 3: Implement Spec 04 RAG Freshness Decay

**Files:**
- Modify: `api/agents/search_agent.py` — Replace `_freshness_score()` with day-based decay; add `_apply_freshness_decay()` 
- Modify: `api/core/rag_store.py` — Return `updated_at` in `RagSearchHit`; add freshness-aware `search_with_freshness()`

- [ ] **Step 1: Replace _freshness_score in search_agent.py**

In `api/agents/search_agent.py`, replace the existing `_published_year_score` and `_freshness_score` functions (lines ~160-185) with:

```python
def _freshness_score(published: str) -> int:
    """Compute freshness score using spec 04 day-based decay.
    
    freshness_score = max(0, 100 - days_since_ingestion × 2)
    Falls back to year-based heuristic if published date cannot be parsed.
    """
    from datetime import datetime, timezone
    
    # Try to parse published date
    if published and published != "未知":
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m"):
            try:
                dt = datetime.strptime(published.strip()[:10], fmt)
                days = max(0, (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days)
                return max(0, 100 - days * 2)
            except (ValueError, IndexError):
                continue
    
    # Fallback: year-based heuristic
    import re
    match = re.search(r"(20\d{2})", str(published))
    if match:
        year = int(match.group(1))
        current_year = datetime.now(timezone.utc).year
        if year == current_year:
            return 85
        if year == current_year - 1:
            return 65
        if year == current_year - 2:
            return 45
        return 25
    return 50  # Unknown date: neutral score


def _apply_freshness_decay(quality_score: float, freshness_score: int) -> tuple[float, bool]:
    """Apply freshness decay multiplier per spec 04 section 3.3.
    
    Returns (adjusted_score, may_be_stale).
    """
    if freshness_score >= 80:
        return quality_score, False
    if freshness_score >= 60:
        return quality_score * 0.85, False
    if freshness_score >= 40:
        return quality_score * 0.7, False
    return quality_score * 0.5, True
```

- [ ] **Step 2: Apply freshness decay in _build_evidence_item**

In `_build_evidence_item()` (line 386-409), after calculating `quality_score`, apply freshness decay:

```python
    freshness_score = _freshness_score(source.published)
    base_score = 55 + freshness_score // 4 + (10 if company_specific else 0) + (8 if source_class in {"company_profile", "jd"} else 0)
    quality_score = max(25, min(100, base_score))
    
    # Apply freshness decay per spec 04 section 3.3
    quality_score, may_be_stale = _apply_freshness_decay(quality_score, freshness_score)
    
    source_id = f"rag-source-{index}" if source.query == "rag_vector_search" else f"source-{index}"
    return {
        "source_id": source_id,
        "source_class": source_class,
        "query": source.query,
        "url": source.url,
        "title": source.title,
        "snippet": source.snippet,
        "published": source.published,
        "relevance_hint": relevance_hint,
        "company_specific": company_specific,
        "freshness_score": freshness_score,
        "quality_score": quality_score,
        "may_be_stale": may_be_stale,
    }
```

- [ ] **Step 3: Add freshness to RAG store search results**

In `api/core/rag_store.py`, update the `RagSearchHit` dataclass to include `updated_at`:

```python
@dataclass(frozen=True)
class RagSearchHit:
    chunk: RagChunk
    score: float
    updated_at: str = ""  # NEW: for freshness decay
```

Update the `search()` method query to return `updated_at`:

In `search()` (line 196), change the SELECT:
```python
    cursor.execute(
        """
        SELECT chunk_id, document_id, source_type, title, url, text, metadata,
               1 - (embedding <=> %s) AS score,
               updated_at
        FROM job_chunks
        WHERE source_type = ANY(%s)
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (embedding, list(ALLOWED_SOURCE_TYPES), embedding, int(top_k)),
    )
```

And update the row unpacking:
```python
    for row in rows:
        chunk_id, document_id, source_type, title, url, text, metadata, score, updated_at = row
        hits.append(
            RagSearchHit(
                chunk=RagChunk(...),
                score=float(score or 0.0),
                updated_at=str(updated_at or ""),
            )
        )
```

Add a `search_with_freshness()` method that applies decay:

```python
    async def search_with_freshness(
        self, *, query: str, profile: dict[str, Any], top_k: int
    ) -> list[RagSearchHit]:
        """Search with freshness decay applied per spec 04 section 3.3."""
        from datetime import datetime, timezone
        
        hits = await self.search(query=query, profile=profile, top_k=top_k)
        now = datetime.now(timezone.utc)
        
        for hit in hits:
            if not hit.updated_at:
                continue
            try:
                updated = datetime.strptime(str(hit.updated_at)[:19], "%Y-%m-%dT%H:%M:%S")
                updated = updated.replace(tzinfo=timezone.utc)
                days = max(0, (now - updated).days)
                freshness = max(0, 100 - days * 2)
                
                if freshness >= 80:
                    pass  # No decay
                elif freshness >= 60:
                    object.__setattr__(hit, 'score', hit.score * 0.85)
                elif freshness >= 40:
                    object.__setattr__(hit, 'score', hit.score * 0.7)
                else:
                    object.__setattr__(hit, 'score', hit.score * 0.5)
            except (ValueError, TypeError):
                pass
        
        return hits
```

- [ ] **Step 4: Run search-related tests**

Run: `python -m pytest tests/test_search_agent_cache.py tests/test_search_agent_rag.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add api/agents/search_agent.py api/core/rag_store.py
git commit -m "feat: implement spec 04 RAG freshness decay with day-based scoring"
```

---

### Task 4: Integration Verification

**Files:**
- All modified files (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -q --timeout=60`
Expected: All previously passing tests still pass

- [ ] **Step 2: Verify context duplication is fixed**

Run a quick manual verification that checks context isn't duplicated:

```bash
python -c "
# Verify context pattern: analysis_agent returns only new_context, not accumulated
import ast, sys
with open('api/agents/analysis_agent.py') as f:
    tree = ast.parse(f.read())
# Find the return statement in run_analysis_agent
for node in ast.walk(tree):
    if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
        keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
        if 'context' in keys:
            # Check it's 'new_context' not 'context'
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and k.value == 'context':
                    if isinstance(v, ast.Name) and v.id == 'new_context':
                        print('PASS: analysis_agent returns new_context (only new items)')
                    elif isinstance(v, ast.Name) and v.id == 'context':
                        print('FAIL: analysis_agent still returns accumulated context')
print('VERIFICATION COMPLETE')
"
```

- [ ] **Step 3: Commit final verification**

```bash
git add -A
git commit -m "chore: Phase 4 integration verification complete"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Task |
|---|---|
| 05-conversation-memory-spec.md — LTM pgvector semantic search | Task 2 |
| 04-rag-spec.md — Section 3.3 freshness decay formula `max(0, 100 - days × 2)` | Task 3 |
| 04-rag-spec.md — Section 3.3 decay tiers (80/60/40 thresholds) | Task 3 |
| Context duplication bug (code review finding #6 from Phase 3) | Task 1 |

### Placeholder Scan

No TBD, TODO, "implement later", or vague references. Every step has exact code. Every file path is exact. Every command has expected output.

### Type Consistency

- `vector_search_fn` signature: `(query: str, user_id: str, top_k: int) -> list[MemoryHit]` — consistent between `retrieve_memories()` (declared) and `_vector_search` (defined in Task 2 Step 3)
- `_apply_freshness_decay` returns `tuple[float, bool]` — consistent with call site in `_build_evidence_item`
- `RagSearchHit.updated_at: str` — matches the SQL `updated_at` column type (TIMESTAMPTZ cast to str)
- `search_by_vector` returns `list[dict[str, Any]]` — adapted to `list[MemoryHit]` by `_vector_search` wrapper in `memory_retrieval.py`
