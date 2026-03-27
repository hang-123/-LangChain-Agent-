"""
Wrapper around LangChain chat models to keep prompts and parsing logic together.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI

from ..config import QueryEngineConfig
from ..prompts import (
    FORMAT_PROMPT,
    REFLECTION_PROMPT,
    SEARCH_PLAN_PROMPT,
    STRUCTURE_PROMPT,
    SUMMARY_PROMPT,
    ParagraphBlueprint,
    ReflectionOutput,
    SearchPlan,
    StructureOutput,
)
from ..state import ParagraphPlan, SearchResult


class LLMOrchestrator:
    """High-level helper that exposes each reasoning step as an async method."""

    def __init__(self, config: QueryEngineConfig):
        llm_kwargs = {"model": config.llm_model, "temperature": config.temperature}
        if config.llm_base_url:
            llm_kwargs["base_url"] = config.llm_base_url
        if config.llm_api_key:
            llm_kwargs["api_key"] = config.llm_api_key

        self.llm = ChatOpenAI(**llm_kwargs)
        self.structure_parser = PydanticOutputParser(pydantic_object=StructureOutput)
        self.plan_parser = PydanticOutputParser(pydantic_object=SearchPlan)
        self.reflection_parser = PydanticOutputParser(pydantic_object=ReflectionOutput)
        self.summary_parser = StrOutputParser()
        self.format_parser = StrOutputParser()
        self.structure_prompt = STRUCTURE_PROMPT.partial(
            format_instructions=self.structure_parser.get_format_instructions()
        )
        self.plan_prompt = SEARCH_PLAN_PROMPT.partial(
            format_instructions=self.plan_parser.get_format_instructions()
        )
        self.reflection_prompt = REFLECTION_PROMPT.partial(
            format_instructions=self.reflection_parser.get_format_instructions()
        )
        self.config = config

    async def generate_structure(self, query: str) -> StructureOutput:
        chain = self.structure_prompt | self.llm | self.structure_parser
        return await chain.ainvoke({"query": query, "max_paragraphs": self.config.max_paragraphs})

    async def plan_search(self, paragraph: ParagraphPlan, query: str) -> SearchPlan:
        chain = self.plan_prompt | self.llm | self.plan_parser
        return await chain.ainvoke(
            {
                "title": paragraph.title,
                "expectation": paragraph.expectation,
                "summary": paragraph.latest_summary or "pending",
                "query": query,
            }
        )

    async def summarize(self, paragraph: ParagraphPlan, query: str, results: List[SearchResult]) -> str:
        snippets = []
        for result in results:
            content = result.content.strip().replace("\n", " ")
            snippets.append(f"- {result.title}\n  {content[:400]}... [{result.url}]")
        payload = "\n".join(snippets) or "暂无有效结果"
        chain = SUMMARY_PROMPT | self.llm | self.summary_parser
        return await chain.ainvoke(
            {
                "title": paragraph.title,
                "expectation": paragraph.expectation,
                "query": query,
                "snippets": payload,
            }
        )

    async def reflect(self, paragraph: ParagraphPlan) -> ReflectionOutput:
        chain = self.reflection_prompt | self.llm | self.reflection_parser
        return await chain.ainvoke(
            {
                "title": paragraph.title,
                "expectation": paragraph.expectation,
                "summary": paragraph.latest_summary,
            }
        )

    async def format_report(self, report_title: str, paragraphs: List[ParagraphPlan]) -> str:
        paragraph_text = "\n".join(
            f"{idx + 1}. {p.title}\nExpectation: {p.expectation}\nSummary:\n{p.latest_summary}\n"
            for idx, p in enumerate(paragraphs)
        )
        chain = FORMAT_PROMPT | self.llm | self.format_parser
        return await chain.ainvoke(
            {
                "title": report_title,
                "timestamp": datetime.utcnow().isoformat(),
                "paragraphs": paragraph_text,
            }
        )
