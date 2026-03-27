# InsightEngineLC/state/state.py
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class InsightReport(BaseModel):
    """最终的结构化舆情报告结果。"""

    question: str
    keywords: List[str] = Field(default_factory=list)
    main_concerns: List[str] = Field(default_factory=list)
    positive_points: List[str] = Field(default_factory=list)
    negative_points: List[str] = Field(default_factory=list)
    sentiment_summary: str = ""
    risks: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    sentiment_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="情感分布，如 {'positive': 10, 'neutral': 5, 'negative': 7}",
    )


class InsightState(BaseModel):
    """
    整条思维链的状态，节点之间通过它传递信息，类似原微舆的 state/state.py。
    """

    question: str
    keywords: List[str] = Field(default_factory=list)
    documents: List[Dict] = Field(default_factory=list)  # 原始检索结果（文档对象字典）
    raw_docs: str = ""                    # 兼容旧节点的合并文本
    db_results: List[Dict] = Field(default_factory=list, description="DB 风格话题查询结果")
    kg_facts: List[Dict] = Field(default_factory=list, description="知识图谱结构化事实")
    sentiment_breakdown: Dict[str, int] = Field(default_factory=dict)
    report: Optional[InsightReport] = None
    markdown_report: Optional[str] = None

