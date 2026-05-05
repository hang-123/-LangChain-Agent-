from __future__ import annotations

from api.core.policy_loader import coerce_policy, load_policy


def test_load_default_policy_contains_expected_sections():
    policy = load_policy()
    assert policy.report_policy.renderer_first is True
    assert "## 一、岗位与公司概览" in policy.report_policy.required_sections
    assert policy.retry_policy.max_retries == 3


def test_coerce_policy_accepts_partial_override_dict():
    policy = coerce_policy({"retry_policy": {"max_retries": 5}})
    assert policy.retry_policy.max_retries == 5
    assert policy.report_policy.title == "专属求职研究报告"
