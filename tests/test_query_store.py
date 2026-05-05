from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from api.core.executor import ResearchExecutionSession
from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings


class QueryStoreGraph:
    async def astream_events(self, _state, version="v2"):
        assert version == "v2"
        yield {"event": "on_node_start", "name": "ReportAgent", "metadata": {"langgraph_node": "ReportAgent"}}
        yield {
            "event": "on_node_end",
            "name": "ReportAgent",
            "metadata": {"langgraph_node": "ReportAgent"},
            "data": {
                "output": {
                    "report_content": "# 专属求职研究报告\n\n## 一、岗位与公司概览\n\n## 二、岗位能力要求拆解\n\n## 三、真实面经与面试官追问\n\n## 四、候选人风险点与准备建议\n\n## 五、一周行动清单\n\n## 附：证据来源\n\nhttps://example.com/a\nhttps://example.com/b",
                    "insights": {
                        "company": "字节跳动",
                        "role": "后端开发实习",
                        "evidence_count": 4,
                        "company_specific_source_count": 2,
                        "action_plan_source_coverage": 80,
                        "quality_metrics": {"claim_evidence_coverage": 75},
                        "fallback_flags": {"query": False, "insight": False, "report": False},
                    },
                    "status": "report done",
                }
            },
        }


@pytest.mark.asyncio
async def test_repository_dual_writes_into_sqlite_query_store(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_QUERY_STORE", "1")
    monkeypatch.setenv("QUERY_STORE_PATH", str(tmp_path / "query_store.sqlite"))
    get_settings.cache_clear()
    repo = FileHarnessRepository(tmp_path / "harness")
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: repo)

    session = ResearchExecutionSession(QueryStoreGraph(), "字节后端实习")
    events = [event async for event in session.stream_events()]

    assert events[-1]["type"] == "done"
    db_path = Path(str(tmp_path / "query_store.sqlite"))
    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        runs_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        traces_count = connection.execute("SELECT COUNT(*) FROM run_traces").fetchone()[0]

    assert runs_count == 1
    assert traces_count >= 2

    get_settings.cache_clear()
