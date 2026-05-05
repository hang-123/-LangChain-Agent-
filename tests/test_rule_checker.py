from __future__ import annotations

from api.review.rule_checker import run_rule_checker


def test_rule_checker_uses_policy_defined_required_sections():
    state = {
        "policy": {
            "report_policy": {
                "required_sections": ["## 自定义章节"],
                "section_order": ["## 自定义章节"],
            }
        },
        "report_content": "# 标题\n\n## 自定义章节\n内容\nhttps://example.com/a\nhttps://example.com/b",
        "insights": {
            "technical_stack_requirements": ["Python", "Redis"],
            "evidence_map": {"technical_stack_requirements": ["source-1"]},
            "company_specific_source_count": 2,
            "action_plan_source_coverage": 80,
        },
        "evidence_items": [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}],
    }
    result = run_rule_checker(state)
    assert not any(issue.issue_code == "missing_markdown_section" for issue in result.issue_details)


def test_rule_checker_routes_missing_tech_stack_to_query():
    state = {
        "report_content": "# 标题\n\n## 一、岗位与公司概览\n\n## 二、岗位能力要求拆解\n\n## 三、真实面经与面试官追问\n?\n\n## 四、候选人风险点与准备建议\n风险\n\n## 五、一周行动清单\nDay 1\n\n## 附：证据来源\nhttps://example.com/a\nhttps://example.com/b",
        "insights": {
            "company_specific_source_count": 2,
            "action_plan_source_coverage": 80,
            "evidence_map": {},
        },
        "evidence_items": [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}],
    }
    result = run_rule_checker(state)
    assert any(issue.issue_code == "missing_tech_stack" and issue.retry_target == "query" for issue in result.issue_details)
