from __future__ import annotations

from pathlib import Path

from ..config import ReportEngineConfig
from ..state import ReportState
from .base import ReportNode


class RenderNode(ReportNode):
    name = "report_render"

    def __init__(self, config: ReportEngineConfig):
        self.config = config
        self.templates_dir = Path(__file__).resolve().parent.parent / "templates"

    def _select_template_path(self) -> Path:
        # 根据配置的 template_id 选择模板文件，不存在时回退到 default
        template_id = (self.config.template_id or "default").strip()
        candidate = self.templates_dir / f"{template_id}.md"
        if candidate.exists():
            return candidate
        return self.templates_dir / "default.md"

    async def arun(self, state: ReportState) -> ReportState:
        if not state.title:
            state.title = f"{state.query} 求职研究报告"

        sections_blocks = []
        for idx, section in enumerate(state.sections, start=1):
            blocks = [f"### {idx}. {section.title}", "", section.summary or "（暂无内容）", ""]
            sections_blocks.append("\n".join(blocks))
        sections_markdown = "\n".join(sections_blocks) or "（暂无详细章节）"

        template_path = self._select_template_path()
        try:
            template = template_path.read_text(encoding="utf-8")
        except FileNotFoundError:  # pragma: no cover
            state.final_markdown = (
                f"# {state.title}\n\n## 一、求职摘要\n\n"
                f"{state.executive_summary or '暂无总结。'}\n\n## 二、详细章节\n\n{sections_markdown}"
            )
            return state

        markdown = (
            template.replace("{title}", state.title)
            .replace("{executive_summary}", state.executive_summary or "暂无总结。")
            .replace("{sections_markdown}", sections_markdown)
        )
        state.final_markdown = markdown
        return state
