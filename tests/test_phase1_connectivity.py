"""Phase 1 connectivity test — Gate, Settings, Constants, Contracts."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure api/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.core.settings import get_settings
from api.core.constants import FORBIDDEN_PHRASES, ARCHETYPE_KEYWORDS, TAILOR_KEYWORDS, PHASE2_INTENTS, WORKFLOW_IDS
from api.core.contracts import SupervisorResponse, GateOutput, InterviewPrepPack, GateStatus
from api.core.gate import run_gate


def test_settings():
    s = get_settings()
    assert s.enable_legitimacy_scorer is True
    assert s.enable_archetype_detector is True
    assert s.report_temperature == 0.5
    assert s.analysis_temperature == 0.3
    assert s.enable_report_self_review is True
    assert s.search_cache_ttl == 600
    assert s.enable_rag_writeback is False
    print("✓ Settings OK")


def test_constants():
    assert len(FORBIDDEN_PHRASES) >= 5
    assert "精通" in FORBIDDEN_PHRASES
    assert "AI Platform / LLMOps" in ARCHETYPE_KEYWORDS
    assert len(TAILOR_KEYWORDS) >= 10
    assert len(PHASE2_INTENTS) == 8
    assert "wf_match_v2" in WORKFLOW_IDS
    print("✓ Constants OK")


def test_contracts():
    from api.core.contracts import QueryProfile
    sr = SupervisorResponse(
        intent="match",
        workflow_id="wf_match_v2",
        query_profile=QueryProfile(company="字节跳动", role="后端开发"),
        reasoning="test",
    )
    assert sr.intent == "match"
    assert sr.workflow_id == "wf_match_v2"

    ip = InterviewPrepPack(prep_id="p1")
    assert ip.prep_id == "p1"
    print("✓ Contracts OK")


def test_gate_passed():
    result = run_gate(
        report_content="这是一个正常的报告，包含了有效的证据分析。",
        min_evidence_count=0,
        min_company_specific=0,
    )
    assert result.status == "passed"
    assert len(result.checked_rules) == 6
    print("✓ Gate passed OK")


def test_gate_rejected_forbidden():
    result = run_gate(
        report_content="这位候选人精通Java，一定过筛。",
        min_evidence_count=0,
        min_company_specific=0,
    )
    assert result.status == "rejected", f"Expected rejected, got {result.status}"
    assert any("精通" in str(i) for i in result.issues)
    print("✓ Gate rejected (forbidden) OK")


def test_gate_downgraded_evidence():
    result = run_gate(
        working_set={"retrieval": {"evidence_items": [{"company_specific": False}]}},
        report_content="测试报告",
        min_evidence_count=4,
        min_company_specific=2,
    )
    assert result.status == "downgraded", f"Expected downgraded, got {result.status}"
    print("✓ Gate downgraded OK")


if __name__ == "__main__":
    test_settings()
    test_constants()
    test_contracts()
    test_gate_passed()
    test_gate_rejected_forbidden()
    test_gate_downgraded_evidence()
    print("\n=== Phase 1 connectivity: ALL TESTS PASSED ===")
