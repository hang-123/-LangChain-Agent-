# InsightEngineLC/nodes/formatting_node.py
from InsightEngine.nodes.base_node import BaseNode
from InsightEngine.state.state import InsightState, InsightReport


class FormattingNode(BaseNode):
    name = "formatting_node"

    @staticmethod
    def _render_markdown(report: InsightReport, sentiment_breakdown: dict) -> str:
        lines = []
        lines.append("# 舆情洞察报告\n")
        lines.append(f"**原始问题：** {report.question}\n")
        lines.append(f"**分析关键词：** {', '.join(report.keywords) or '（暂无）'}\n")

        def render_list(title: str, items):
            lines.append(f"## {title}")
            if not items:
                lines.append("- （暂无）")
            else:
                for i, item in enumerate(items, start=1):
                    lines.append(f"- {i}. {item}")
            lines.append("")

        render_list("一、主要关注点（Main Concerns）", report.main_concerns)
        render_list("二、正面观点（Positive Points）", report.positive_points)
        render_list("三、负面观点（Negative Points）", report.negative_points)

        lines.append("## 四、整体情绪概览（Sentiment Summary）")
        lines.append(report.sentiment_summary or "（暂无）")
        lines.append("")

        if sentiment_breakdown:
            pos = sentiment_breakdown.get("positive", 0)
            neu = sentiment_breakdown.get("neutral", 0)
            neg = sentiment_breakdown.get("negative", 0)
            total = max(pos + neu + neg, 1)
            lines.append("### 情绪分布（Sentiment Breakdown）")
            lines.append(f"- 正向：{pos}（约 {int(pos / total * 100)}%）")
            lines.append(f"- 中性：{neu}（约 {int(neu / total * 100)}%）")
            lines.append(f"- 负向：{neg}（约 {int(neg / total * 100)}%）")
            lines.append("")

        render_list("五、潜在风险（Risks）", report.risks)
        render_list("六、建议（Suggestions）", report.suggestions)

        return "\n".join(lines)

    def run(self, state: InsightState) -> InsightState:
        if state.report is None:
            raise ValueError("FormattingNode: state.report 为空，前置节点未正确生成报告。")

        state.markdown_report = self._render_markdown(
            state.report, state.sentiment_breakdown
        )
        return state
