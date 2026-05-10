from __future__ import annotations

import json

import pytest

from api.agents.report_agent import report_agent_node


def _good_report() -> str:
    return """# 专属求职研究报告

> 研究目标：分析 Databricks 后端岗位
> 目标公司：Databricks
> 目标岗位：Backend Engineer

## 一、岗位与公司概览
Databricks 强调数据基础设施和分布式系统能力，这类岗位通常要求候选人能把后端工程能力放进数据平台的业务语境里解释。
从公开岗位线索和面经线索看，Databricks 更看重工程判断、系统设计取舍、以及围绕数据链路稳定性的表达，而不是只罗列通用后端技能。
如果候选人只能泛泛谈 CRUD、接口开发和缓存优化，而不能把这些经验映射到数据平台、离线链路或在线分析服务，就很难让面试官相信匹配度足够高。

## 二、岗位能力要求拆解
### 公司特异性要求
- 熟悉数据平台工程
- 能把分布式系统设计经验转成 Databricks 关心的数据基础设施表达
- 理解数据链路可靠性、吞吐、成本之间的平衡

### 通用要求
- 具备扎实后端工程基础
- 能清晰解释系统拆分、容量评估、稳定性治理和排障过程

### 真实技术栈 / JD 要求
- Python
- Spark
- SQL
- 分布式系统设计

### 面试官期待画像
- 能解释系统设计取舍
- 能把项目经历讲成可验证的工程决策，而不是抽象结论

## 三、真实面经与面试官追问
- 你如何权衡数据一致性与吞吐？
- 如果上游数据波动导致下游计算延迟，你会先看哪些指标？
- 当一个数据平台服务既要支持实时查询又要控制成本时，你怎么做架构取舍？
这类问题背后考察的不是背诵术语，而是候选人能否把容量、延迟、可靠性、成本、故障恢复和团队协作放进同一个叙事里。
如果回答中只有“用了缓存”“做了异步化”“做了分库分表”这种抽象表述，没有明确说明触发条件、观察指标、取舍过程和最终结果，Databricks 这类岗位通常不会给高分。

## 四、候选人风险点与准备建议
### 风险点提示
- Go 经验较弱，可能影响特定团队匹配。
- 如果不能把项目经验和 Databricks 的数据平台语境绑定起来，面试官会质疑理解深度。
- 如果回答里缺少真实指标、权衡过程和失败复盘，风险不只是“表达不清”，而是会被判断为没有独立 ownership。

### 准备建议
- 补一页分布式系统设计案例。
- 准备一个围绕吞吐、延迟、一致性、稳定性折中的项目复盘。
- 把现有项目中的数据流、瓶颈点和优化取舍整理成面试可复述的结构化提纲。

### 证据缺口
- 还缺少最新团队级面经。
- 还缺少更直接说明 Databricks 团队方向差异的最新岗位资料。
当前判断仍然建立在公开岗位与公开面经的交叉印证上，还缺少足够多能说明具体团队差异、组织边界和业务优先级的最近期证据。
因此最终报告可以支持“有条件匹配”的结论，但暂时不适合给出“高度匹配、面试稳过”这类高置信度表述。

> 面试官视角定性：基础不错，但需要更强的数据平台语境表达。

## 五、一周行动清单
### Day 1 · 补齐系统设计证据
- 优先级：high
- 任务：整理一个数据链路设计案例
- 为什么是这家公司：Databricks 强调数据基础设施
- 预期产出：一页讲解提纲
- 证据绑定：https://example.com/a
- 复盘重点：把一致性、吞吐、成本和稳定性之间的取舍讲清楚，并明确你本人负责的关键决策

### Day 2 · 强化岗位特异性表达
- 优先级：medium
- 任务：重写项目总结
- 为什么是这家公司：Databricks 的数据平台岗位要求候选人把项目经验翻译成数据基础设施表达
- 预期产出：改写后的项目 bullet
- 证据绑定：https://example.com/b
- 复盘重点：每条 bullet 都补齐场景、指标、动作、结果，避免只写“负责”和“参与”

### Day 3 · 准备高压追问答案
- 优先级：medium
- 任务：为“为什么这么设计”“为什么不是另一种方案”准备口头答案
- 为什么是这家公司：Databricks 面试会追问工程取舍和系统设计判断
- 预期产出：一页追问问答卡片
- 证据绑定：https://example.com/a

### 行动清单说明
以上行动项不是固定模板，而是围绕 Databricks 当前更强调的数据基础设施、系统设计解释力、以及证据绑定表达来安排优先级。
如果 Day 1 和 Day 2 的准备质量不足，Day 3 的高压追问训练会失去基础，因此执行顺序不能随意调换。
完成这些动作后，候选人至少应该能把一个项目讲清楚：场景是什么、约束是什么、为什么这么设计、做了什么、结果如何、哪些地方还能优化。

## 附：证据来源
| 证据类别 | 来源 URL | 标题 | 相关性说明 | 关键摘要 |
| --- | --- | --- | --- | --- |
| jd | https://example.com/a | JD | 岗位要求 | 数据平台 |
| interview | https://example.com/b | Interview | 面经追问 | 分布式系统 |
"""


@pytest.mark.asyncio
async def test_report_agent_embeds_self_review_feedback(monkeypatch):
    async def _no_polish(**_kwargs):
        return None

    async def _no_mild_review(**_kwargs):
        return None

    monkeypatch.setattr("api.agents.report_agent._polish_fragments", _no_polish)
    monkeypatch.setattr("api.agents.report_agent._mild_llm_review", _no_mild_review)
    monkeypatch.setattr("api.agents.report_agent.render_report_markdown", lambda **_kwargs: "# bad\n\nshort")

    state = {
        "run_id": "run-test",
        "query": "分析岗位",
        "context": [],
        "insights": {"company": "Databricks", "role": "Backend Engineer"},
        "retry_count": 0,
        "policy": {},
    }
    result = await report_agent_node(state)
    feedback = json.loads(result["review_feedback"])

    assert feedback["passed"] is False
    assert result["root_cause"]
    assert "内置自审发现问题" in result["status"]


@pytest.mark.asyncio
async def test_report_agent_marks_self_review_pass(monkeypatch):
    async def _no_polish(**_kwargs):
        return None

    async def _no_mild_review(**_kwargs):
        return None

    monkeypatch.setattr("api.agents.report_agent._polish_fragments", _no_polish)
    monkeypatch.setattr("api.agents.report_agent._mild_llm_review", _no_mild_review)
    monkeypatch.setattr("api.agents.report_agent.render_report_markdown", lambda **_kwargs: _good_report())

    state = {
        "run_id": "run-test",
        "query": "分析岗位",
        "context": [],
        "insights": {
            "company": "Databricks",
            "role": "Backend Engineer",
            "technical_stack_requirements": ["Python", "Spark"],
            "company_specific_requirements": ["熟悉数据平台工程"],
            "interviewer_questions": ["你如何权衡数据一致性与吞吐？"],
            "candidate_risks": ["Go 经验较弱"],
            "prep_strategy": ["补一页分布式系统设计案例"],
            "action_plan_items": [
                {
                    "day": 1,
                    "priority": "high",
                    "goal": "补齐系统设计证据",
                    "task": "整理一个数据链路设计案例",
                    "why_this_company": "Databricks 强调数据基础设施",
                    "expected_outcome": "一页讲解提纲",
                    "evidence_refs": ["https://example.com/a"],
                },
                {
                    "day": 2,
                    "priority": "medium",
                    "goal": "强化岗位特异性表达",
                    "task": "重写项目总结",
                    "why_this_company": "Databricks 的数据平台岗位要求候选人把项目经验翻译成数据基础设施表达",
                    "expected_outcome": "改写后的项目 bullet",
                    "evidence_refs": ["https://example.com/b"],
                },
                {
                    "day": 3,
                    "priority": "medium",
                    "goal": "准备高压追问答案",
                    "task": "为“为什么这么设计”“为什么不是另一种方案”准备口头答案",
                    "why_this_company": "Databricks 面试会追问工程取舍和系统设计判断",
                    "expected_outcome": "一页追问问答卡片",
                    "evidence_refs": ["https://example.com/a"],
                },
            ],
            "action_plan_source_coverage": 80,
            "evidence_map": {
                "technical_stack_requirements": [
                    "https://example.com/a",
                    "https://example.com/b",
                ]
            },
            "quality_metrics": {"claim_evidence_coverage": 80},
        },
        "evidence_items": [
            {"url": "https://example.com/a"},
            {"url": "https://example.com/b"},
        ],
        "context": ["https://example.com/a", "https://example.com/b"],
        "policy": {},
    }
    result = await report_agent_node(state)
    feedback = json.loads(result["review_feedback"])

    assert feedback["passed"] is True
    assert "内置自审通过" in result["status"]
