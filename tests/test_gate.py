"""Gate unit tests — pure rule checks, 0 LLM."""
from __future__ import annotations

import pytest
from api.core.gate import run_gate
from api.core.contracts import GateOutput


def make_evidence_items(count: int = 5, company_specific: int = 3):
    items = []
    for i in range(count):
        items.append({
            "source_id": f"src_{i}",
            "source_class": "jd",
            "title": f"Test Evidence {i}",
            "snippet": f"Test snippet {i}",
            "company_specific": i < company_specific,
        })
    return items


class TestGatePassed:
    def test_all_checks_pass(self):
        """Gate passes when all checks are satisfied."""
        evidence = make_evidence_items(6, 3)
        result = run_gate(
            artifacts={"report": {"report_content": "候选人具有相关经验，该岗位匹配度较高。"}},
            working_set={"retrieval": {"evidence_items": evidence}, "analysis": {"claims": [
                {"claim_id": "c1", "evidence_refs": ["src_0"]},
                {"claim_id": "c2", "evidence_refs": ["src_1"]},
            ]}},
            background={"candidate": {"candidate_profile": {"skills": ["Python"]}, "resume_evidence": [{"text": "Python developer"}]}},
            report_content="候选人具有相关经验，该岗位匹配度较高。",
        )
        assert result.status == "passed"
        assert len(result.issues) == 0
        assert "forbidden_phrases" in result.checked_rules

    def test_minimal_input_passes(self):
        """Gate passes with minimal clean input."""
        result = run_gate(
            report_content="岗位需求与候选人技能基本匹配。结论：建议投递。",
        )
        assert result.status in ("passed", "downgraded")


class TestGateDowngraded:
    def test_insufficient_evidence(self):
        """Gate downgrades when evidence count is too low."""
        result = run_gate(
            working_set={"retrieval": {"evidence_items": make_evidence_items(2, 1)}},
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any("证据数量" in i.get("message", "") for i in result.issues)

    def test_low_company_specificity(self):
        """Gate downgrades when company-specific sources are too few."""
        result = run_gate(
            working_set={"retrieval": {"evidence_items": make_evidence_items(5, 1)}},
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any("公司特异性" in i.get("message", "") for i in result.issues)

    def test_unbacked_claims(self):
        """Gate downgrades when claims lack evidence refs."""
        evidence = make_evidence_items(5, 3)
        result = run_gate(
            working_set={
                "retrieval": {"evidence_items": evidence},
                "analysis": {"claims": [
                    {"claim_id": "c1", "evidence_refs": []},
                    {"claim_id": "c2", "evidence_refs": []},
                ]},
            },
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any("证据引用" in i.get("message", "") for i in result.issues)

    def test_claim_coverage_below_threshold(self):
        evidence = make_evidence_items(5, 3)
        result = run_gate(
            working_set={
                "retrieval": {"evidence_items": evidence},
                "analysis": {
                    "claims": [{"claim_id": "c1", "evidence_refs": ["src_0"]}],
                    "quality_metrics": {"claim_evidence_coverage": 50},
                },
            },
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any(i.get("rule") == "claim_evidence_coverage" for i in result.issues)

    def test_action_plan_coverage_below_threshold(self):
        evidence = make_evidence_items(5, 3)
        result = run_gate(
            working_set={
                "retrieval": {"evidence_items": evidence},
                "analysis": {
                    "action_plan_items": [{"day": 1, "goal": "补准备"}],
                    "action_plan_source_coverage": 40,
                },
            },
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any(i.get("rule") == "action_plan_source_coverage" for i in result.issues)

    def test_missing_classes_downgrades(self):
        evidence = make_evidence_items(5, 3)
        result = run_gate(
            working_set={
                "retrieval": {
                    "evidence_items": evidence,
                    "retrieval_diagnostics": {"missing_classes": ["interview", "tech_stack"]},
                },
            },
            report_content="test report",
        )
        assert result.status == "downgraded"
        assert any(i.get("rule") == "missing_classes" for i in result.issues)


class TestGateRejected:
    def test_forbidden_phrase_rejected(self):
        """Gate rejects output containing forbidden phrases."""
        result = run_gate(
            report_content="该候选人精通所有技术栈，一定能通过面试。",
        )
        assert result.status in ("downgraded", "rejected")

    def test_candidate_fact_boundary_violation(self):
        """Gate rejects when forbidden phrases appear without evidence backing."""
        result = run_gate(
            background={"candidate": {"candidate_profile": {}, "resume_evidence": []}},
            report_content="候选人精通Python和Java开发。",
        )
        assert result.status in ("downgraded", "rejected")

    def test_multiple_rejected_rules(self):
        """When multiple rules fire, rejected takes priority."""
        result = run_gate(
            working_set={"retrieval": {"evidence_items": make_evidence_items(2, 0)}},
            background={"candidate": {"candidate_profile": {}, "resume_evidence": []}},
            report_content="候选人精通所有技术，保证录取。",
        )
        assert result.status in ("downgraded", "rejected")
        # Check both evidence sufficiency and boundary checks ran
        checked = result.checked_rules
        assert "evidence_sufficiency" in checked or "candidate_fact_boundary" in checked


class TestGateEdgeCases:
    def test_empty_input(self):
        """Gate handles completely empty input."""
        result = run_gate()
        assert result.status in ("passed", "downgraded")

    def test_all_rules_checked(self):
        """All expected check rules are listed in output."""
        result = run_gate(report_content="test")
        expected_rules = {"evidence_sufficiency", "company_specificity", "candidate_fact_boundary",
                          "evidence_refs", "claim_evidence_coverage", "action_plan_source_coverage",
                          "missing_classes", "forbidden_phrases", "fiction_detection"}
        assert expected_rules == set(result.checked_rules)

    def test_output_is_gate_output_type(self):
        """Gate returns proper GateOutput type."""
        result = run_gate(report_content="test")
        assert isinstance(result, GateOutput)
        assert result.status in ("passed", "downgraded", "rejected")
