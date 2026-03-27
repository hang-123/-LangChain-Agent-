from __future__ import annotations

import json
import traceback
from typing import Any
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ForumEngine.forum import ForumEngine
from utils.logger import _write as _log_raw


class ForumRunRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question or topic.")
    template_id: str | None = Field(
        default=None,
        description="Optional report template id (e.g. default, executive, analysis).",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional existing session id for multi-turn memory.",
    )


class ForumMessage(BaseModel):
    speaker: str
    content: str
    metadata: dict[str, Any] | None = None
    timestamp: str


class ForumRunResponse(BaseModel):
    session_id: str
    messages: List[ForumMessage]
    report_markdown: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    error_type: str | None = None


app = FastAPI(
    title="Career Research Assistant API",
    version="1.0.0",
    description="多Agent求职研究助手 API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
forum_engine = ForumEngine()


def _log_forum_exception(context: str, exc: Exception) -> str:
    trace = traceback.format_exc()
    payload = f"{context}: {exc!r}\n{trace}"
    try:
        _log_raw("forum_error", payload)
    except Exception:
        pass
    print(payload)
    return trace


@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "career-research-assistant"}


@app.post("/api/forum/run", response_model=ForumRunResponse)
async def run_forum(payload: ForumRunRequest) -> ForumRunResponse:
    """
    运行多 Agent 求职研究流程并生成报告
    
    - **query**: 用户的岗位、公司或面试准备问题
    - **template_id**: 可选的报告模板ID (default, executive, analysis)
    - **session_id**: 可选的会话ID，用于多轮对话记忆
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")
    
    try:
        session = forum_engine.run_session(
            query,
            template_id=payload.template_id,
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _log_forum_exception("run_forum", exc)
        raise HTTPException(
            status_code=500,
            detail=f"ForumEngine failed: {str(exc)}",
        ) from exc

    messages = [
        ForumMessage(
            speaker=msg.speaker,
            content=msg.content,
            metadata=msg.metadata,
            timestamp=msg.timestamp,
        )
        for msg in session.messages
    ]
    report_content = next(
        (msg.content for msg in session.messages if msg.speaker == "ReportAgent"),
        None,
    )
    return ForumRunResponse(
        session_id=session.session_id or "",
        messages=messages,
        report_markdown=report_content,
    )


@app.get("/api/forum/stream")
async def stream_forum(
    query: str = Query(..., min_length=1, description="User question or topic."),
    template_id: str | None = Query(
        default=None, description="Optional report template id."
    ),
    session_id: str | None = Query(
        default=None, description="Optional existing session id."
    ),
):
    """
    流式运行论坛引擎，通过 Server-Sent Events 返回状态与消息事件。

    - **query**: 用户的岗位、公司或面试准备问题
    - **template_id**: 可选的报告模板ID
    - **session_id**: 可选的会话ID
    """
    clean_query = query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    async def event_generator() -> AsyncIterator[str]:
        try:
            for event in forum_engine.stream_session(
                clean_query,
                template_id=template_id,
                session_id=session_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            _log_forum_exception("stream_forum.validation", exc)
            error_payload = {
                "type": "error",
                "error_type": "validation_error",
                "detail": f"请求参数错误: {str(exc)}",
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            return
        except Exception as exc:
            trace = _log_forum_exception("stream_forum.runtime", exc)
            error_payload = {
                "type": "error",
                "error_type": "runtime_error",
                "detail": f"ForumEngine执行失败: {str(exc)}",
                "traceback": trace,
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=9000, reload=True)
