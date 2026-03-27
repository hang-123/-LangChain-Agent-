# InsightEngineLC/nodes/sentiment_node.py
from InsightEngine.nodes.base_node import BaseNode
from InsightEngine.state.state import InsightState
from InsightEngine.tools.sentiment_tool import analyze_sentiment_distribution


class SentimentNode(BaseNode):
    name = "sentiment_node"

    def run(self, state: InsightState) -> InsightState:
        state.sentiment_breakdown = analyze_sentiment_distribution(state.raw_docs)
        return state
