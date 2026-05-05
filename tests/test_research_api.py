from __future__ import annotations

from fastapi.testclient import TestClient

from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings
from api.main import app


class FakeRunGraph:
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
        yield {"event": "on_node_start", "name": "QueryAgent", "metadata": {"langgraph_node": "QueryAgent"}}
        yield {
            "event": "on_node_end",
            "name": "QueryAgent",
            "metadata": {"langgraph_node": "QueryAgent"},
            "data": {
                "output": {
                    "insights": {"company": "字节跳动", "role": "后端开发实习"},
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
                    "status": "query done",
                }
            },
        }
        yield {"event": "on_node_start", "name": "ReportAgent", "metadata": {"langgraph_node": "ReportAgent"}}
        yield {
            "event": "on_node_end",
            "name": "ReportAgent",
            "metadata": {"langgraph_node": "ReportAgent"},
            "data": {
                    "output": {
                        "report_content": "# 专属求职研究报告",
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
                        "insights": {"company": "字节跳动", "role": "后端开发实习"},
                        "quality_mode": "normal",
                        "root_cause": "retrieval",
                    "status": "report done",
                }
            },
        }


def test_run_research_returns_job_intelligence_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr("api.main._graph", FakeRunGraph())
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post("/api/research/run", json={"query": "帮我研究字节跳动后端开发实习"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_snapshot"]["job_snapshot_id"] == "js::job::字节跳动::后端开发实习"
    assert payload["external_evidence_pack"]["evidence_pack_id"] == "jep::job::字节跳动::后端开发实习"
    assert payload["match_assessment"]["assessment_id"] == "match::cand_001::job::字节跳动::后端开发实习"
    assert payload["tailor_plan"]["tailor_plan_id"].startswith("rtp::")
    assert payload["resume_version"]["fact_check_status"] == "passed"
    assert payload["fact_check_report"]["status"] == "passed"

    get_settings.cache_clear()


def test_run_research_rejects_malformed_tailoring_payload(monkeypatch, tmp_path):
    monkeypatch.setattr("api.main._graph", FakeRunGraph())
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/research/run",
        json={
            "query": "帮我研究字节跳动后端开发实习",
            "candidate_profile": {"candidate_id": "cand_001"},
            "resume_evidence": [
                {
                    "resume_id": "resume_raw_001",
                    "evidence_type": "project",
                    "section": "projects",
                    "text": "在订单系统项目中使用 Redis。",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "resume_evidence[1] must include evidence_id" in response.text

    response = client.post(
        "/api/research/run",
        json={
            "query": "帮我研究字节跳动后端开发实习",
            "candidate_profile": {"candidate_id": "cand_001"},
        },
    )

    assert response.status_code == 422
    assert "candidate_profile and resume_evidence must be provided together" in response.text

    get_settings.cache_clear()


def test_stream_research_accepts_structured_resume_tailor_payload(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakeStructuredSession:
        def __init__(
            self,
            graph,
            query,
            *,
            candidate_profile=None,
            resume_evidence=None,
            job_posting=None,
            match_assessment=None,
            research_case=None,
        ):
            captured["graph"] = graph
            captured["query"] = query
            captured["candidate_profile"] = candidate_profile
            captured["resume_evidence"] = resume_evidence
            captured["job_posting"] = job_posting
            captured["match_assessment"] = match_assessment
            captured["research_case"] = research_case
            self.state = {"run_id": "run-test"}

        async def stream_events(self):
            yield {
                "type": "meta",
                "run_id": "run-test",
                "query": str(captured["query"]),
                "max_retries": 3,
                "started_at": "2026-04-19T10:00:00Z",
                "timestamp": "2026-04-19T10:00:00Z",
            }
            yield {
                "type": "done",
                "run_id": "run-test",
                "node": "System",
                "timestamp": "2026-04-19T10:00:01Z",
                "report_markdown": "# ok",
            }

    monkeypatch.setattr("api.main.ResearchExecutionSession", FakeStructuredSession)
    monkeypatch.setattr("api.main._graph", object())
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/research/stream",
        json={
            "query": "我有一份简历和目标岗位，请按 wf_resume_tailor_v2 输出改写计划。",
            "candidate_profile": {"candidate_id": "cand_001", "skills": ["Redis"]},
            "resume_evidence": [
                {
                    "evidence_id": "evi_001",
                    "section": "projects",
                    "text": "在订单系统项目中使用 Redis。",
                }
            ],
            "job_posting": {"job_title": "后端开发工程师"},
            "match_assessment": {"assessment_id": "match_001", "candidate_id": "cand_001", "job_id": "job_001"},
        },
    )

    assert response.status_code == 200
    assert captured["query"] == "我有一份简历和目标岗位，请按 wf_resume_tailor_v2 输出改写计划。"
    assert captured["candidate_profile"] == {"candidate_id": "cand_001", "skills": ["Redis"]}
    assert captured["resume_evidence"] == [
        {
            "evidence_id": "evi_001",
            "section": "projects",
            "text": "在订单系统项目中使用 Redis。",
        }
    ]
    assert captured["job_posting"] == {"job_title": "后端开发工程师"}
    assert captured["match_assessment"] == {
        "assessment_id": "match_001",
        "candidate_id": "cand_001",
        "job_id": "job_001",
    }

    get_settings.cache_clear()
