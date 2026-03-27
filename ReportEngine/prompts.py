"""
Prompt templates for the ReportEngine.
"""

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


class ReportPlanOutput(BaseModel):
    executive_summary: str = Field(default="", description="High level summary.")
    sections: list[dict] = Field(default_factory=list, description="List of {'title','summary'}.")


REPORT_PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an AI career research lead. Combine multiple agent outputs into a job-search action plan. "
            "Sources are grouped like [External Web Research], [Internal Insights], [Media Signals]. "
            "Produce an executive summary for a candidate, then propose sections focused on role fit, company context, "
            "interview preparation, and next actions. Respond only with JSON per schema.\n"
            "{format_instructions}",
        ),
        (
            "human",
            "Candidate goal: {query}\n"
            "Sources:\n"
            "{sources}",
        ),
    ]
)
