"""
LangChain prompt templates for the MediaEngine pipeline.
"""

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


class MediaSummaryOutput(BaseModel):
    highlights: list[str] = Field(default_factory=list, description="Key narratives spotted online.")
    emerging_risks: list[str] = Field(default_factory=list, description="Potential negative signals.")
    sentiment_overview: str = Field(default="", description="Overall tone.")
    visual_references: list[str] = Field(default_factory=list, description="Notable images or videos.")


MEDIA_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior media analyst. Given merged multimedia search snippets, "
            "identify the most important highlights, risks, sentiment trends, and notable visuals. "
            "Return JSON exactly matching the schema.\n{format_instructions}",
        ),
        (
            "human",
            "User query: {query}\n"
            "Evidence snippets:\n"
            "------------------\n"
            "{evidence}\n"
            "------------------",
        ),
    ]
)


MEDIA_FORMAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Compose a polished markdown media brief with sections: Overview, Highlights, Risks, "
            "Sentiment Outlook, Visual References. Keep it concise but actionable.",
        ),
        (
            "human",
            "Query: {query}\n"
            "Highlights: {highlights}\n"
            "Risks: {risks}\n"
            "Sentiment: {sentiment}\n"
            "Visual references: {visuals}",
        ),
    ]
)

