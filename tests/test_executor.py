from __future__ import annotations

import pytest

from api.core.executor import ResearchExecutionSession
from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings


class FakeGraph:
    async def astream_events(self, _state, version="v2"):
        assert version == "v2"
        yield {"event": "on_node_start", "name": "IntentRouterNode", "metadata": {"langgraph_node": "IntentRouterNode"}}
        yield {
            "event": "on_node_end",
            "name": "IntentRouterNode",
            "metadata": {"langgraph_node": "IntentRouterNode"},
            "data": {
                "output": {
                    "intent": "general",
                    "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
                    "insights": {"intent_reason": "test"},
                    "status": "intent done",
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
                    "match_assessment": {
                        "assessment_id": "match::cand_001::job::字节跳动::后端开发实习",
                        "candidate_id": "cand_001",
                        "job_id": "job::字节跳动::后端开发实习",
                        "overall_score": 76,
                        "recommendation": "recommended_with_risks",
                    },
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
    assert done_event["tailor_plan"]["tailor_plan_id"].startswith("rtp::")
    assert done_event["resume_version"]["fact_check_status"] == "passed"
    assert done_event["fact_check_report"]["status"] == "passed"
    assert len(done_event["trace"]) >= 4
    assert session.state["root_cause_history"][-1]["root_cause"] == "retrieval"
