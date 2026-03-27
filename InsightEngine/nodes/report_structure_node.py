# InsightEngineLC/nodes/report_structure_node.py
from InsightEngine.nodes.base_node import BaseNode
from InsightEngine.state.state import InsightState


class ReportStructureNode(BaseNode):
    """
    目前只负责保证 report 不为空，将来可以扩展为：
    - 根据问题类型选择不同的结构模板
    - 给 report 增加额外字段（例如行业、竞争对手板块等）
    """

    name = "report_structure_node"

    def run(self, state: InsightState) -> InsightState:
        if state.report is None:
            # 理论上 SummaryNode 应该已经生成，这里兜底
            from InsightEngine.state.state import InsightReport

            state.report = InsightReport(
                question=state.question,
                keywords=state.keywords,
                main_concerns=[],
            )
        return state
