from __future__ import annotations

from api.core.perf import NodePerfTracker


def test_node_perf_tracker_builds_perf_bill_with_estimated_tokens():
    tracker = NodePerfTracker("run-test")
    tracker.start_node("ReportAgent")
    tracker.observe_lang_event(
        "ReportAgent",
        {
            "event": "on_chat_model_start",
            "metadata": {"langgraph_node": "ReportAgent", "model_name": "qwen-plus"},
            "data": {"input": {"messages": [{"content": "请生成报告"}]}},
        },
    )
    tracker.observe_lang_event(
        "ReportAgent",
        {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_node": "ReportAgent", "model_name": "qwen-plus"},
            "data": {"chunk": {"content": "报告正文"}},
        },
    )
    tracker.observe_lang_event(
        "ReportAgent",
        {
            "event": "on_tool_start",
            "metadata": {"langgraph_node": "ReportAgent"},
            "data": {},
        },
    )
    node_perf = tracker.complete_node("ReportAgent")
    bill = tracker.build_bill()

    assert node_perf.llm_calls == 1
    assert node_perf.tool_calls == 1
    assert node_perf.token_total > 0
    assert node_perf.token_estimated is True
    assert bill.node_count == 1
    assert bill.total_llm_calls == 1
