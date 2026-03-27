# from langchain.agents import create_agent
#
# from InsightEngine.llms.base import get_llm
# from InsightEngine.tools.local_search import search_local_docs
#
# def build_insight_agent():
#     """
#         使用 LangChain 1.0 的 create_agent 创建一个简化版 Insight Agent。
#
#         - model: ChatOpenAI 实例
#         - tools: [search_local_docs]
#         - system_prompt: 定义“舆情分析师”的角色
#         """
#     model = get_llm()
#     tools = [search_local_docs]
#
#     system_prompt = (
#         "你是一名中文舆情分析师，擅长阅读舆情文档，"
#         "总结用户关注点、情绪倾向和潜在风险，并给出简短、可行动的建议。\n"
#         "你可以使用提供的 search_local_docs 工具在本地舆情文档中检索信息。\n"
#         "如果你需要具体事实或原文，请优先调用工具，而不是胡乱猜测。"
#     )
#
#     agent = create_agent(
#         model=model,
#         tools=tools,
#         system_prompt=system_prompt,
#     )
#
#     return agent


# InsightEngineLC/agent.py
from InsightEngine.state.state import InsightState
from InsightEngine.nodes.search_node import SearchNode
from InsightEngine.nodes.summary_node import SummaryNode
from InsightEngine.nodes.report_structure_node import ReportStructureNode
from InsightEngine.nodes.formatting_node import FormattingNode
from InsightEngine.nodes.sentiment_node import SentimentNode  # 如果你建了这个文件
from InsightEngine.tools.keyword_optimizer import optimize_keywords
from utils.logger import log_agent_run


class InsightAgent:
    """
    LangChain 版 InsightEngine：
    question -> keywords -> search -> sentiment -> summary -> structure -> formatting
    """

    def __init__(self):
        self.nodes = [
            SearchNode(),
            SentimentNode(),
            SummaryNode(),
            ReportStructureNode(),
            FormattingNode(),
        ]

    def run(self, question: str) -> InsightState:
        # 初始 state
        state = InsightState(
            question=question,
            keywords=optimize_keywords(question),
        )

        for node in self.nodes:
            state = node(state)

        if state.markdown_report:
            summary = state.markdown_report[:200] + "..."
        elif state.report and state.report.main_concerns:
            summary = "; ".join(state.report.main_concerns[:3])
        else:
            summary = "No insight markdown generated."
        log_agent_run("insight", question, summary=summary)

        return state
