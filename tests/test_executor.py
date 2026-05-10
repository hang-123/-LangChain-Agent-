from __future__ import annotations

import pytest

from api.core.executor import ResearchExecutionSession
from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings


class FakeGraph:
    async def astream_events(self, _state, version="v2"):
        assert version == "v2"
        yield {"event": "on_node_start", "name": "Supervisor", "metadata": {"langgraph_node": "Supervisor"}}
        yield {
            "event": "on_node_end",
            "name": "Supervisor",
            "metadata": {"langgraph_node": "Supervisor"},
            "data": {
                "output": {
                    "intent": "general",
                    "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
                    "insights": {"intent_reason": "test"},
                    "status": "intent done",
                }
            },
        }
        yield {"event": "on_node_start", "name": "JobAnalyzer", "metadata": {"langgraph_node": "JobAnalyzer"}}
        yield {
            "event": "on_node_end",
            "name": "JobAnalyzer",
            "metadata": {"langgraph_node": "JobAnalyzer"},
            "data": {
                "output": {
                    "external_evidence_pack": {
                        "evidence_pack_id": "jep::job::字节跳动::后端开发实习",
                        "job_id": "job::字节跳动::后端开发实习",
                        "sources": [{"source_id": "source-1", "source_type": "jd"}],
                    },
                    "job_snapshot": {
                        "job_snapshot_id": "js::job::字节跳动::后端开发实习",
                        "job_id": "job::字节跳动::后端开发实习",
                        "external_evidence_pack_id": "jep::job::字节跳动::后端开发实习",
                    },
                    "status": "job intelligence done",
                }
            },
        }
        yield {"event": "on_node_start", "name": "MatchingEngine", "metadata": {"langgraph_node": "MatchingEngine"}}
        yield {
            "event": "on_node_end",
            "name": "MatchingEngine",
            "metadata": {"langgraph_node": "MatchingEngine"},
            "data": {
                "output": {
                    "match_assessment": {
                        "assessment_id": "match::cand_001::job::字节跳动::后端开发实习",
                        "candidate_id": "cand_001",
                        "job_id": "job::字节跳动::后端开发实习",
                        "overall_score": 76,
                        "recommendation": "recommended_with_risks",
                    },
                    "status": "matching done",
                }
            },
        }
        yield {"event": "on_node_start", "name": "ResumeTailor", "metadata": {"langgraph_node": "ResumeTailor"}}
        yield {
            "event": "on_node_end",
            "name": "ResumeTailor",
            "metadata": {"langgraph_node": "ResumeTailor"},
            "data": {
                "output": {
                    "tailor_plan": {
                        "tailor_plan_id": "rtp::cand_001::job::字节跳动::后端开发实习",
                        "candidate_id": "cand_001",
                        "job_id": "job::字节跳动::后端开发实习",
                    },
                    "resume_version": {
                        "resume_version_id": "resume::cand_001::job::字节跳动::后端开发实习",
                        "candidate_id": "cand_001",
                        "job_id": "job::字节跳动::后端开发实习",
                        "fact_check_status": "passed",
                    },
                    "fact_check_report": {
                        "verification_id": "ver::resume::cand_001::job::字节跳动::后端开发实习",
                        "artifact_type": "resume_version",
                        "artifact_id": "resume::cand_001::job::字节跳动::后端开发实习",
                        "status": "passed",
                    },
                    "status": "resume tailor done",
                }
            },
        }
        yield {"event": "on_node_start", "name": "ReportAgent", "metadata": {"langgraph_node": "ReportAgent"}}
        yield {
            "event": "on_chat_model_stream",
            "name": "ReportAgent",
            "metadata": {"langgraph_node": "ReportAgent"},
            "data": {"chunk": "hello"},
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
                        "fallback_flags": {"query": False, "insight": False, "report": False},
                    },
                    "quality_mode": "normal",
                    "root_cause": "retrieval",
                    "status": "report done",
                }
            },
        }


@pytest.mark.asyncio
async def test_execution_session_emits_run_id_metrics_and_trace(monkeypatch, tmp_path):
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()
    session = ResearchExecutionSession(FakeGraph(), "test query")
    events = [event async for event in session.stream_events()]

    assert events[0]["type"] == "meta"
    assert events[0]["run_id"].startswith("run-")
    assert events[0]["run_manifest"]["policy_version"]
    assert any(event["type"] == "chunk" and event["content"] == "hello" for event in events)
    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["quality_summary"]["evidence_count"] == 5
    assert done_event["job_snapshot"]["job_snapshot_id"] == "js::job::字节跳动::后端开发实习"
    assert done_event["external_evidence_pack"]["evidence_pack_id"] == "jep::job::字节跳动::后端开发实习"
    assert done_event["match_assessment"]["assessment_id"] == "match::cand_001::job::字节跳动::后端开发实习"
    assert done_event["workflow_state"]["artifacts"]["job"]["job_snapshot"]["job_snapshot_id"] == (
        "js::job::字节跳动::后端开发实习"
    )
    assert done_event["workflow_state"]["control"]["root_cause"] == "retrieval"
    assert done_event["workflow_state"]["telemetry"]["quality_summary"]["evidence_count"] == 5
    assert done_event["tailor_plan"]["tailor_plan_id"].startswith("rtp::")
    assert done_event["resume_version"]["fact_check_status"] == "passed"
    assert done_event["fact_check_report"]["status"] == "passed"
    assert len(done_event["trace"]) >= 10
    assert session.state["root_cause_history"][-1]["root_cause"] == "retrieval"


@pytest.mark.asyncio
async def test_execution_session_loads_and_saves_conversation_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_CONVERSATION_MEMORY", "1")
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    saved: dict[str, object] = {}

    class FakeMemoryStore:
        async def load_latest(self, user_id: str):
            assert user_id == "user_001"
            from api.core.conversation_memory import ConversationMemorySnapshot

            return ConversationMemorySnapshot(
                user_id="user_001",
                conversation_id="conv::user_001",
                summary="上一轮分析的是字节后端实习。",
                artifact_refs={"job_snapshot_id": "js_prev"},
                updated_at="2026-05-06T00:00:00Z",
            )

        async def save_turn(self, **kwargs):
            saved.update(kwargs)

    monkeypatch.setattr("api.core.executor.build_conversation_memory_store", lambda: FakeMemoryStore())

    session = ResearchExecutionSession(FakeGraph(), "继续改简历", user_id="user_001")
    events = [event async for event in session.stream_events()]

    assert events[-1]["memory_used"] is True
    assert "上一轮分析的是字节后端实习" in events[-1]["conversation_summary"]
    assert session.state["memory_summary"] == "上一轮分析的是字节后端实习。"
    assert saved["user_id"] == "user_001"
    assert saved["run_id"] == session.state["run_id"]

    get_settings.cache_clear()
