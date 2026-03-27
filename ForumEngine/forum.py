from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

from utils.logger import log_forum_message
from utils.session_memory import (
    append_session_message,
    build_memory_snippet,
    create_session,
    get_memory_mode,
)

from .config import ForumEngineConfig
from .minimal_agents import (
    MinimalInsightAgent,
    MinimalQueryAgent,
    MinimalReportAgent,
    build_smalltalk_reply,
    detect_query_mode,
)
from .state import ForumMessage, ForumSession

def _augment_query_with_history(query: str, history_snippet: str) -> str:
    """
    将历史对话片段拼接到当前查询后面，作为辅助说明。
    """

    history = history_snippet.strip()
    if not history:
        return query

    return (
        f"{query}\n\n"
        "（以下是本会话中之前的若干轮对话与系统结论，仅作参考，请以当前问题为主：\n"
        f"{history}\n"
        "）"
    )


def _build_reference_context(history_snippet: str) -> str | None:
    """
    将 memory 片段包装成明确的“参考上下文”，避免被下游当成当前问题主体。
    """

    history = history_snippet.strip()
    if not history:
        return None
    return (
        "以下历史信息仅作参考，当前问题优先级更高。\n"
        f"{history}"
    )


@dataclass
class ForumEngine:
    # 使用 default_factory 避免 dataclass 可变默认值问题
    config: ForumEngineConfig = field(default_factory=ForumEngineConfig)

    def __post_init__(self) -> None:
        self.query_agent = MinimalQueryAgent()
        self.insight_agent = MinimalInsightAgent()
        self.report_agent = MinimalReportAgent()

    def run_session(
        self,
        query: str,
        template_id: str | None = None,
        session_id: Optional[str] = None,
    ) -> ForumSession:
        return self._run_session_impl(query, template_id=template_id, session_id=session_id)

    def stream_session(
        self,
        query: str,
        template_id: str | None = None,
        session_id: Optional[str] = None,
    ) -> Iterator[dict]:
        if session_id:
            conversation_id = session_id
        else:
            conversation_id = create_session(topic=query)

        session = ForumSession(query=query, session_id=conversation_id)
        yield {"type": "meta", "session_id": conversation_id}

        if self.config.use_memory and session_id:
            history_snippet = build_memory_snippet(
                conversation_id,
                query,
                limit=self.config.memory_history_limit,
                max_chars=self.config.memory_max_chars,
            )
            reference_context = _build_reference_context(history_snippet)
        else:
            reference_context = None

        if self.config.use_memory:
            append_session_message(
                conversation_id,
                role="user",
                agent="User",
                content=query,
                metadata={
                    "memory_mode": get_memory_mode(conversation_id),
                },
            )

        if detect_query_mode(query) == "smalltalk":
            reply = build_smalltalk_reply(query)
            system_message = self._store_agent_message(
                session,
                conversation_id,
                "System",
                reply,
            )
            log_forum_message("System", f"完成闲聊回复: {query}")
            yield self._message_event(system_message)
            yield {"type": "done", "session_id": session.session_id}
            return

        yield self._status_event("QueryAgent", "started", "正在解析岗位、公司与求职目标")
        query_result = self.query_agent.run(
            query,
            template_id=template_id,
            save_report=self.config.save_individual_reports,
        )
        query_message = self._store_agent_message(
            session,
            conversation_id,
            "QueryAgent",
            query_result.report_markdown,
            metadata=query_result.metadata,
        )
        log_forum_message("QueryAgent", f"完成岗位信息提炼: {query}")
        yield self._message_event(query_message)
        yield self._status_event("QueryAgent", "completed", "已完成岗位与公司基础信息提炼")

        yield self._status_event("InsightAgent", "started", "正在整理候选人视角洞察")
        insight_result = self.insight_agent.run(
            query,
            query_result.metadata,
            template_id=template_id,
            memory_context=reference_context,
        )
        insight_md = insight_result.report_markdown
        insight_message = self._store_agent_message(
            session,
            conversation_id,
            "InsightAgent",
            insight_md,
            metadata=insight_result.metadata,
        )
        log_forum_message("InsightAgent", f"完成内部洞察: {query}")
        yield self._message_event(insight_message)
        yield self._status_event("InsightAgent", "completed", "已完成岗位要求与候选人匹配分析")

        sources: List[Tuple[str, str]] = [
            ("Role And Company Scan", query_result.report_markdown),
            ("Candidate Insight", insight_md),
        ]

        yield self._status_event("ReportAgent", "started", "正在生成结构化求职行动报告")
        report_result = self.report_agent.run(
            query,
            sources,
            template_id=template_id,
            save_report=self.config.save_individual_reports,
            memory_context=reference_context,
        )
        report_message = self._store_agent_message(
            session,
            conversation_id,
            "ReportAgent",
            report_result.report_markdown,
            metadata=report_result.metadata,
        )
        log_forum_message("ReportAgent", f"完成综合报告: {query}")
        yield self._message_event(report_message)
        yield self._status_event("ReportAgent", "completed", "已输出求职研究报告与行动建议")
        yield {"type": "done", "session_id": session.session_id}

    def _run_session_impl(
        self,
        query: str,
        template_id: str | None = None,
        session_id: Optional[str] = None,
    ) -> ForumSession:
        # 1. 确定会话 ID，并在必要时创建 conversations 记录
        if session_id:
            conversation_id = session_id
        else:
            conversation_id = create_session(topic=query)

        session = ForumSession(query=query, session_id=conversation_id)

        # 2. 如启用记忆，则加载历史消息并拼接到 query；否则保持纯本轮问题
        if self.config.use_memory and session_id:
            history_snippet = build_memory_snippet(
                conversation_id,
                query,
                limit=self.config.memory_history_limit,
                max_chars=self.config.memory_max_chars,
            )
            reference_context = _build_reference_context(history_snippet)
        else:
            reference_context = None

        # 3. 如启用记忆，则记录当前用户问题到 DB（仅存储，不参与当前 prompt）
        if self.config.use_memory:
            append_session_message(
                conversation_id,
                role="user",
                agent="User",
                content=query,
                metadata={
                    "memory_mode": get_memory_mode(conversation_id),
                },
            )

        if detect_query_mode(query) == "smalltalk":
            reply = build_smalltalk_reply(query)
            self._store_agent_message(
                session,
                conversation_id,
                "System",
                reply,
            )
            log_forum_message("System", f"完成闲聊回复: {query}")
            return session

        # 4. 依次调用各个 Agent
        query_result = self.query_agent.run(
            query,
            template_id=template_id,
            save_report=self.config.save_individual_reports,
        )
        self._store_agent_message(
            session,
            conversation_id,
            "QueryAgent",
            query_result.report_markdown,
            metadata=query_result.metadata,
        )
        log_forum_message("QueryAgent", f"完成岗位信息提炼: {query}")

        insight_result = self.insight_agent.run(
            query,
            query_result.metadata,
            template_id=template_id,
            memory_context=reference_context,
        )
        insight_md = insight_result.report_markdown
        self._store_agent_message(
            session,
            conversation_id,
            "InsightAgent",
            insight_md,
            metadata=insight_result.metadata,
        )
        log_forum_message("InsightAgent", f"完成内部洞察: {query}")

        sources: List[Tuple[str, str]] = [
            ("Role And Company Scan", query_result.report_markdown),
            ("Candidate Insight", insight_md),
        ]

        report_result = self.report_agent.run(
            query,
            sources,
            template_id=template_id,
            save_report=self.config.save_individual_reports,
            memory_context=reference_context,
        )
        self._store_agent_message(
            session,
            conversation_id,
            "ReportAgent",
            report_result.report_markdown,
            metadata=report_result.metadata,
        )
        log_forum_message("ReportAgent", f"完成综合报告: {query}")

        return session

    def _store_agent_message(
        self,
        session: ForumSession,
        conversation_id: str,
        speaker: str,
        content: str,
        metadata: dict | None = None,
    ) -> ForumMessage:
        session.add_message(speaker, content, metadata=metadata)
        message = session.messages[-1]
        if self.config.use_memory:
            append_session_message(
                conversation_id,
                role="assistant",
                agent=speaker,
                content=content,
                metadata=metadata,
            )
        return message

    @staticmethod
    def _status_event(agent: str, phase: str, detail: str) -> dict:
        return {
            "type": "status",
            "agent": agent,
            "phase": phase,
            "detail": detail,
        }

    @staticmethod
    def _message_event(message: ForumMessage) -> dict:
        return {
            "type": "message",
            "speaker": message.speaker,
            "content": message.content,
            "metadata": message.metadata,
            "timestamp": message.timestamp,
        }
