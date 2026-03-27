"""
Prompt templates and response schemas for the LangChain Query Agent.
"""

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import AliasChoices, BaseModel, Field


class ParagraphBlueprint(BaseModel):
    title: str = Field(..., description="Section heading.")
    expectation: str = Field(
        ...,
        description="What the section must cover.",
        validation_alias=AliasChoices("expectation", "description"),
    )


class StructureOutput(BaseModel):
    report_title: str = Field(
        default="洞察报告",
        validation_alias=AliasChoices("report_title", "title"),
    )
    paragraphs: list[ParagraphBlueprint] = Field(
        default_factory=list,
        validation_alias=AliasChoices("paragraphs", "sections"),
    )


STRUCTURE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Design up to {max_paragraphs} research sections for a public opinion study. "
            "Respond ONLY in JSON following these instructions:\n{format_instructions}",
        ),
        ("human", "User query: {query}"),
    ]
)


class SearchPlan(BaseModel):
    search_query: str = Field(..., description="Concrete keyword phrase.")
    tool: str = Field(
        ...,
        description=(
            "One of basic_search_news, deep_search_news, search_news_last_24_hours, "
            "search_news_last_week, search_news_by_date, search_images_for_news, "
            "internal_vector_search (use for company/internal topics), "
            "internal_kg_search (use when asking about relations between entities or events)."
        ),
    )
    start_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD start date when using search_news_by_date.",
    )
    end_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD end date when using search_news_by_date.",
    )


SEARCH_PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Plan the next search for this paragraph. Respond ONLY in JSON per:\n{format_instructions}\n"
            "- Tools: basic_search_news, deep_search_news, search_news_last_24_hours, search_news_last_week,\n"
            "  search_news_by_date (requires start_date/end_date), search_images_for_news,\n"
            "  internal_vector_search, internal_kg_search.\n"
            "- Use internal_vector_search when the topic concerns company/internal matters.\n"
            "- Use internal_kg_search when the question is about relationships, causality, or evolution between entities/events.\n"
            "- Provide start_date/end_date in YYYY-MM-DD when selecting search_news_by_date; otherwise omit them.",
        ),
        (
            "human",
            "Paragraph: {title}\nExpectation: {expectation}\nCurrent summary: {summary}\nUser query: {query}",
        ),
    ]
)


SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior analyst. Turn curated search snippets into an evidence-based paragraph. "
            "Always cite sources using markdown link syntax.",
        ),
        (
            "human",
            "Paragraph: {title}\nExpectation: {expectation}\nUser query: {query}\nSearch snippets:\n{snippets}",
        ),
    ]
)


class ReflectionOutput(BaseModel):
    needs_more_research: bool
    feedback: str


REFLECTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Review whether the draft summary fully meets the expectation. "
            "Respond ONLY in JSON described here:\n{format_instructions}",
        ),
        (
            "human",
            "Paragraph: {title}\nExpectation: {expectation}\nDraft summary:\n{summary}",
        ),
    ]
)


FORMAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Combine all paragraph summaries into a polished markdown report with a title, "
            "executive summary bullets, and numbered sections.",
        ),
        (
            "human",
            "Title: {title}\nTimestamp: {timestamp}\nParagraphs:\n{paragraphs}",
        ),
    ]
)
