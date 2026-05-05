from __future__ import annotations

from api.core.contracts import (
    ExternalEvidenceItem,
    ExternalEvidencePack,
    FactCheckReport,
    JobSnapshot,
    MatchAssessment,
    ResumeTailoringPlan,
    ResumeVersion,
    VerificationIssue,
    VerificationReport,
)


def test_external_evidence_pack_accepts_mixed_job_sources():
    pack = ExternalEvidencePack(
        evidence_pack_id="jep_001",
        job_id="job_001",
        sources=[
            ExternalEvidenceItem(
                source_id="src_001",
                source_type="job_board",
                title="后端开发实习生",
                url="https://example.com/job",
                snippet="熟悉 Redis、MySQL",
                freshness_score=92,
                confidence=0.88,
                evidence_class="real_jd",
            )
        ],
        company_signals=["交易中台"],
        interview_signals=["缓存设计"],
        risk_flags=["方向混合"],
    )

    assert pack.sources[0].evidence_class == "real_jd"
    assert pack.company_signals == ["交易中台"]


def test_job_snapshot_references_evidence_pack_and_quality_notes():
    snapshot = JobSnapshot(
        job_snapshot_id="js_001",
        job_id="job_001",
        job_posting={},
        job_requirements=[],
        external_evidence_pack_id="jep_001",
        evidence_quality={"freshness": 88, "coverage": 0.81, "ambiguity_notes": ["团队归属存在歧义"]},
    )

    assert snapshot.external_evidence_pack_id == "jep_001"
    assert snapshot.evidence_quality["freshness"] == 88


def test_verification_report_keeps_rule_level_failures():
    report = VerificationReport(
        verification_id="ver_001",
        artifact_type="resume_version",
        artifact_id="resume_v_001",
        status="rejected",
        issues=[
            VerificationIssue(
                rule_code="candidate_fact_boundary",
                severity="high",
                message="岗位证据被写成候选人事实",
            )
        ],
        checked_rules=["candidate_fact_boundary"],
        created_at="2026-04-19T10:00:00Z",
    )

    assert report.status == "rejected"
    assert report.issues[0].rule_code == "candidate_fact_boundary"


def test_match_assessment_keeps_dimension_scores_and_recommendation():
    assessment = MatchAssessment(
        assessment_id="match_001",
        candidate_id="cand_001",
        job_id="job_001",
        overall_score=76,
        recommendation="recommended_with_risks",
        strengths=[{"title": "具备 Redis 项目经验", "evidence_refs": ["evi_001", "req_001"]}],
        gaps=[{"title": "缺少 Kafka 证据", "severity": "medium", "evidence_refs": ["req_002"]}],
        risks=[{"title": "项目指标偏少", "severity": "medium"}],
        dimension_scores={"skills": 80, "experience": 72},
        reasoning_notes=["仅基于简历显式证据评分"],
        created_at="2026-04-19T10:00:00Z",
    )

    assert assessment.recommendation == "recommended_with_risks"
    assert assessment.dimension_scores["skills"] == 80


def test_resume_tailor_contracts_keep_guidance_and_fact_check_status():
    plan = ResumeTailoringPlan(
        tailor_plan_id="rtp_001",
        candidate_id="cand_001",
        job_id="job_001",
        target_role="后端开发工程师",
        headline_suggestion="具备 Java / Redis / MySQL 项目经验的后端候选人",
        keyword_coverage={"covered": ["Java", "Redis"], "missing": ["Kafka"], "overused": []},
        section_actions=[
            {
                "section": "projects",
                "action": "rewrite",
                "instruction": "把订单系统项目改写为更贴近交易中台场景的表达",
                "allowed_evidence_refs": ["evi_resume_001"],
            }
        ],
        risk_notes=["不得补写未在原始简历出现的量化指标"],
    )
    version = ResumeVersion(
        resume_version_id="resume_v_001",
        candidate_id="cand_001",
        job_id="job_001",
        source_resume_id="resume_raw_001",
        version_label="backend-trading-v1",
        summary_text="具备 Java / Redis / MySQL 项目经验的后端候选人",
        project_bullets=["负责订单查询接口优化，接口平均响应时间降低 20%"],
        keyword_insertions=["Redis", "MySQL"],
        omissions=["与目标岗位弱相关的前端经历"],
        fact_check_status="downgraded",
        created_at="2026-04-19T10:00:00Z",
    )
    fact_check = FactCheckReport(
        verification_id="ver_001",
        artifact_type="resume_version",
        artifact_id="resume_v_001",
        status="downgraded",
        blocked_claims=["未将缺失要求 Kafka 写成已掌握事实"],
        checked_rules=["candidate_fact_boundary", "evidence_coverage"],
        created_at="2026-04-19T10:00:00Z",
    )

    assert plan.keyword_coverage["missing"] == ["Kafka"]
    assert version.fact_check_status == "downgraded"
    assert version.fact_check_status == fact_check.status
    assert fact_check.blocked_claims[0].endswith("已掌握事实")
