from __future__ import annotations

from api.core.graph import build_initial_state
from api.core.workflow_state import get_artifacts, get_background, get_control, get_telemetry, get_working_set


def test_workflow_state_views_map_flat_agent_state_into_layers():
    state = build_initial_state(
        "帮我分析字节后端实习是否匹配",
        run_id="run_001",
        candidate_profile={"candidate_id": "cand_001", "skills": ["Redis"]},
        resume_evidence=[{"evidence_id": "evi_001", "text": "使用 Redis"}],
        job_posting={"job_id": "job_001", "job_title": "后端开发实习"},
        policy={"max_retries": 3},
        run_manifest={"policy_version": "test-policy"},
        research_case={"case_id": "case_001"},
    )
    state.update(
        {
            "intent": "general",
            "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
            "query_pack": [{"query": "字节 后端 JD"}],
            "context": ["SOURCE_CLASS: jd\nTITLE: 后端开发实习"],
            "evidence_items": [{"source_id": "source-1", "source_class": "jd"}],
            "retrieval_diagnostics": {"coverage_by_class": {"jd": 1}},
            "insights": {
                "query_result": {"company": "字节跳动"},
                "insight_result": {"candidate_risks": ["项目深挖"]},
                "quality_metrics": {"claim_evidence_coverage": 80},
                "render_metadata": {"sections": 5},
            },
            "review_feedback": "needs shorter report",
            "external_evidence_pack": {"evidence_pack_id": "jep_001"},
            "job_snapshot": {"job_snapshot_id": "js_001"},
            "match_assessment": {"assessment_id": "match_001"},
            "tailor_plan": {"tailor_plan_id": "rtp_001"},
            "resume_version": {"resume_version_id": "resume_v_001"},
            "fact_check_report": {"verification_id": "ver_001"},
            "report_content": "# report",
            "retry_count": 1,
            "quality_mode": "conservative",
            "warning_message": "证据不足",
            "root_cause": "retrieval",
            "root_cause_history": [{"root_cause": "retrieval"}],
            "status": "等待重试",
            "run_trace": [{"node": "SearchAgent"}],
            "quality_summary": {"evidence_count": 1},
            "perf_bill": {"total_duration_ms": 12},
            "perf_bill_path": "logs/perf.json",
            "security_events": [{"reason_code": "prompt_injection"}],
        }
    )

    background = get_background(state)
    working_set = get_working_set(state)
    artifacts = get_artifacts(state)
    control = get_control(state)
    telemetry = get_telemetry(state)

    assert background["run"]["run_id"] == "run_001"
    assert background["run"]["research_case"]["case_id"] == "case_001"
    assert background["request"]["query_profile"]["company"] == "字节跳动"
    assert background["candidate"]["candidate_profile"]["candidate_id"] == "cand_001"
    assert background["job_input"]["job_posting"]["job_title"] == "后端开发实习"
    assert background["policy"]["max_retries"] == 3

    assert working_set["retrieval"]["query_pack"] == [{"query": "字节 后端 JD"}]
    assert working_set["retrieval"]["evidence_items"][0]["source_id"] == "source-1"
    assert working_set["analysis"]["query_result"] == {"company": "字节跳动"}
    assert working_set["analysis"]["insight_result"] == {"candidate_risks": ["项目深挖"]}
    assert working_set["analysis"]["quality_metrics"] == {"claim_evidence_coverage": 80}
    assert working_set["review"]["review_feedback"] == "needs shorter report"

    assert artifacts["job"]["external_evidence_pack"]["evidence_pack_id"] == "jep_001"
    assert artifacts["matching"]["match_assessment"]["assessment_id"] == "match_001"
    assert artifacts["resume"]["fact_check_report"]["verification_id"] == "ver_001"
    assert artifacts["report"]["report_content"] == "# report"

    assert control == {
        "retry_count": 1,
        "quality_mode": "conservative",
        "warning_message": "证据不足",
        "root_cause": "retrieval",
        "root_cause_history": [{"root_cause": "retrieval"}],
        "status": "等待重试",
    }
    assert telemetry["run_trace"] == [{"node": "SearchAgent"}]
    assert telemetry["perf_bill_path"] == "logs/perf.json"


def test_workflow_state_views_return_isolated_copies_with_defaults():
    state = build_initial_state("帮我研究目标岗位")

    background = get_background(state)
    artifacts = get_artifacts(state)

    background["request"]["query"] = "mutated"
    artifacts["job"]["job_snapshot"]["job_snapshot_id"] = "mutated"

    assert state["query"] == "帮我研究目标岗位"
    assert state["job_snapshot"] == {}
    assert get_control(state)["quality_mode"] == "normal"
    assert get_telemetry(state)["security_events"] == []
