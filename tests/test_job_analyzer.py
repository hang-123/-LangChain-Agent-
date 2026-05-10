from __future__ import annotations

import pytest

from api.tools.job_analyzer import run_job_analyzer


@pytest.mark.asyncio
async def test_job_analyzer_populates_external_evidence_signals():
    state = {
        "query_profile": {"company": "Databricks", "role": "Backend Engineer"},
        "evidence_items": [
            {
                "source_id": "cp-1",
                "source_class": "company_profile",
                "title": "Lakehouse platform and distributed data systems",
                "snippet": "The team builds large-scale data infrastructure.",
            },
            {
                "source_id": "iv-1",
                "source_class": "interview",
                "title": "Backend interview focuses on distributed systems",
                "snippet": "Candidates are asked about data infra tradeoffs.",
            },
            {
                "source_id": "sc-1",
                "source_class": "salary_culture",
                "title": "Remote-friendly with strong engineering culture",
                "snippet": "High autonomy and ownership expectations.",
            },
        ],
        "context": [
            "This posting may have repost_count concerns and ambiguous team ownership.",
        ],
    }

    result = await run_job_analyzer(state)
    pack = result["external_evidence_pack"]

    assert pack["company_signals"]
    assert any("Lakehouse" in item or "engineering culture" in item for item in pack["company_signals"])
    assert pack["interview_signals"]
    assert any("distributed systems" in item for item in pack["interview_signals"])


@pytest.mark.asyncio
async def test_job_analyzer_exposes_legitimacy_risks_in_external_pack():
    state = {
        "query_profile": {"company": "TestCo", "role": "Backend Engineer"},
        "evidence_items": [
            {
                "source_id": "cp-1",
                "source_class": "company_profile",
                "title": "Company profile",
                "snippet": "The company announced layoffs affecting 50% of the team.",
            },
        ],
        "raw_jd_text": "This role has expired and requires 10 years of Go for an intern position.",
        "context": [],
    }

    result = await run_job_analyzer(state)
    pack = result["external_evidence_pack"]

    assert result["legitimacy_assessment"]["tier"] in ("Proceed with Caution", "Suspicious")
    assert pack["risk_flags"]
    assert any("岗位合法性" in item or "layoff" in item.lower() or "裁员" in item for item in pack["risk_flags"])
