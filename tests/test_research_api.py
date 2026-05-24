from __future__ import annotations

from fastapi.testclient import TestClient

from api.core.persistence import FileHarnessRepository
from api.core.settings import get_settings
from api.main import app


class FakeRunGraph:
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
        yield {"event": "on_node_start", "name": "SearchOrchestrator", "metadata": {"langgraph_node": "SearchOrchestrator"}}
        yield {
            "event": "on_node_end",
            "name": "SearchOrchestrator",
            "metadata": {"langgraph_node": "SearchOrchestrator"},
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
    assert payload["workflow_state"]["artifacts"]["job"]["job_snapshot"]["job_snapshot_id"] == (
        "js::job::字节跳动::后端开发实习"
    )
    assert payload["workflow_state"]["control"]["root_cause"] == "retrieval"
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

    assert response.status_code == 200

    response = client.post(
        "/api/research/run",
        json={
            "query": "帮我研究字节跳动后端开发实习",
            "candidate_profile": {"candidate_id": "cand_001"},
        },
    )

    assert response.status_code == 200

    get_settings.cache_clear()


def test_stream_research_accepts_structured_resume_tailor_payload(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakeStructuredSession:
        def __init__(
            self,
            graph,
            query,
            *,
            user_id="",
            candidate_profile=None,
            resume_evidence=None,
            job_posting=None,
            match_assessment=None,
            raw_jd_text="",
            resume_file=None,
            offer_list=None,
            research_case=None,
        ):
            captured["graph"] = graph
            captured["query"] = query
            captured["user_id"] = user_id
            captured["candidate_profile"] = candidate_profile
            captured["resume_evidence"] = resume_evidence
            captured["job_posting"] = job_posting
            captured["match_assessment"] = match_assessment
            captured["raw_jd_text"] = raw_jd_text
            captured["resume_file"] = resume_file
            captured["offer_list"] = offer_list
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
                "memory_used": bool(captured["user_id"]),
                "conversation_summary": "上一轮摘要" if captured["user_id"] else "",
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
            "user_id": "user_001",
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
    assert captured["user_id"] == "user_001"
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


def test_run_research_accepts_user_id_and_returns_memory_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_CONVERSATION_MEMORY", "0")
    monkeypatch.setenv("ENABLE_LTM", "0")
    monkeypatch.setattr("api.main._graph", FakeRunGraph())
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/research/run",
        json={"query": "继续分析字节后端实习", "user_id": "user_001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "memory_used" in payload
    assert "conversation_summary" in payload

    get_settings.cache_clear()


def test_run_research_phase2_forwards_job_resume_and_offer_inputs(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakePhase2Session:
        def __init__(
            self,
            graph,
            query,
            *,
            user_id="",
            candidate_profile=None,
            resume_evidence=None,
            job_posting=None,
            match_assessment=None,
            raw_jd_text="",
            resume_file=None,
            offer_list=None,
            research_case=None,
        ):
            captured["graph"] = graph
            captured["query"] = query
            captured["user_id"] = user_id
            captured["raw_jd_text"] = raw_jd_text
            captured["resume_file"] = resume_file
            captured["offer_list"] = offer_list
            captured["research_case"] = research_case
            self.state = {
                "run_id": "run-phase2",
                "report_content": "# phase2 ok",
                "insights": {},
                "quality_summary": {},
                "run_trace": [],
                "run_manifest": {},
                "workflow_id": "wf_profile_bootstrap",
                "profile_completeness": 0.6,
            }

        async def stream_events(self):
            yield {"type": "meta", "run_id": "run-phase2"}
            yield {"type": "done", "run_id": "run-phase2", "report_markdown": "# phase2 ok"}

    monkeypatch.setattr("api.main.ResearchExecutionSession", FakePhase2Session)
    monkeypatch.setattr("api.core.executor.build_repository", lambda policy: FileHarnessRepository(tmp_path / "harness"))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/research/run",
        json={
            "query": "上传简历并分析这个岗位",
            "user_id": "user_phase2",
            "raw_jd_text": "职位描述：负责后端开发和系统设计。",
            "resume_file": {
                "source_type": "txt",
                "source_name": "resume.txt",
                "raw_text": "张三\nJava Python Redis",
            },
            "offer_list": [
                {"offer_id": "offer_a", "north_star_alignment": 80},
                {"offer_id": "offer_b", "north_star_alignment": 70},
            ],
        },
    )

    assert response.status_code == 200
    assert captured["query"] == "上传简历并分析这个岗位"
    assert captured["user_id"] == "user_phase2"
    assert captured["raw_jd_text"] == "职位描述：负责后端开发和系统设计。"
    assert captured["resume_file"] == {
        "source_type": "txt",
        "source_name": "resume.txt",
        "raw_text": "张三\nJava Python Redis",
    }
    assert captured["offer_list"] == [
        {"offer_id": "offer_a", "north_star_alignment": 80},
        {"offer_id": "offer_b", "north_star_alignment": 70},
    ]

    get_settings.cache_clear()
