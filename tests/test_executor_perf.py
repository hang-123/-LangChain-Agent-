from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.core.executor import ResearchExecutionSession
from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings


class PerfGraph:
    async def astream_events(self, _state, version="v2"):
        assert version == "v2"
        yield {"event": "on_node_start", "name": "ReportAgent", "metadata": {"langgraph_node": "ReportAgent"}}
        yield {
            "event": "on_chat_model_start",
            "name": "ChatOpenAI",
            "metadata": {"langgraph_node": "ReportAgent", "model_name": "qwen-plus"},
            "data": {"input": {"messages": [{"content": "请产出报告"}]}},
        }
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "metadata": {"langgraph_node": "ReportAgent", "model_name": "qwen-plus"},
            "data": {"chunk": {"content": "hello"}},
        }
        yield {
            "event": "on_chat_model_end",
            "name": "ChatOpenAI",
            "metadata": {"langgraph_node": "ReportAgent", "model_name": "qwen-plus"},
            "data": {"output": {"content": "hello", "usage_metadata": {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}}},
        }
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
                        "evidence_count": 5,
                        "company_specific_source_count": 3,
                        "action_plan_source_coverage": 80,
                        "quality_metrics": {"claim_evidence_coverage": 75},
                        "fallback_flags": {"query": False, "insight": False, "report": False}
                    },
                    "quality_mode": "normal",
                    "root_cause": "retrieval",
                    "status": "report done"
                }
            },
        }


@pytest.mark.asyncio
async def test_execution_session_writes_perf_bill_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_NODE_PERF", "1")
    get_settings.cache_clear()
    repo = FileHarnessRepository(tmp_path / "harness")
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: repo)

    session = ResearchExecutionSession(PerfGraph(), "test query")
    events = [event async for event in session.stream_events()]

    done_event = events[-1]
    perf_bill_path = Path(str(done_event["perf_bill_path"]))
    assert perf_bill_path.exists()
    payload = json.loads(perf_bill_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == session.state["run_id"]
    assert payload["total_llm_calls"] >= 1
    assert payload["total_token_total"] >= 12

    get_settings.cache_clear()
