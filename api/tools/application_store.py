"""ApplicationStore Tool — CRUD for job application records with legal status flow.

Pure deterministic tool, 0 LLM. Uses SQLite for persistence.
"""

from __future__ import annotations

import time as _time
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "rejected", "withdrawn"},
    "planned": {"applied", "rejected", "withdrawn"},
    "applied": {"screening", "rejected", "withdrawn"},
    "screening": {"written_test", "rejected", "withdrawn"},
    "written_test": {"interviewing", "rejected", "withdrawn"},
    "interviewing": {"offer", "rejected", "withdrawn"},
    "offer": {"rejected", "withdrawn"},
}


def _validate_transition(from_status: str, to_status: str) -> bool:
    if from_status in ("rejected", "withdrawn"):
        return False
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    return to_status in allowed


_last_ts_ns: int = 0


def _now_iso() -> str:
    """Return an ISO-8601 UTC timestamp string.

    Uses nanosecond-resolution time and a module-level counter
    to guarantee monotonically increasing values even for
    extremely rapid successive calls.
    """
    global _last_ts_ns
    now_ns = _time.time_ns()
    if now_ns <= _last_ts_ns:
        now_ns = _last_ts_ns + 1000  # advance by at least 1 microsecond
    _last_ts_ns = now_ns
    return datetime.fromtimestamp(now_ns / 1e9, tz=timezone.utc).isoformat()


class ApplicationStore:
    """SQLite-backed application record store."""

    def __init__(self, db_path: str = "data/application_store.db"):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        import os
        dir_path = os.path.dirname(self.db_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                application_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                company TEXT DEFAULT '',
                role TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                notes_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL
            )
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_candidate
            ON applications(candidate_id)
        """)
        await self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_app_candidate_job
            ON applications(candidate_id, job_id)
        """)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def create_application(
        self,
        candidate_id: str,
        job_id: str,
        company: str = "",
        role: str = "",
        status: str = "draft",
    ) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        # Check for duplicate
        existing = await self.conn.execute(
            "SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?",
            (candidate_id, job_id),
        )
        row = await existing.fetchone()
        if row:
            return {
                "error_code": "duplicate",
                "message": f"Application already exists for candidate={candidate_id} job={job_id}",
                "application_id": row["application_id"],
            }

        app_id = f"app_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        await self.conn.execute(
            """INSERT INTO applications
               (application_id, candidate_id, job_id, company, role, status, notes_json, created_at, last_updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)""",
            (app_id, candidate_id, job_id, company, role, status, now, now),
        )
        await self.conn.commit()

        result = await self.get_application(app_id)
        return result if result is not None else {}

    async def update_status(self, application_id: str, new_status: str) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        current = await self.get_application(application_id)
        if not current:
            return {"ok": False, "error_code": "not_found", "message": f"Application {application_id} not found"}

        if not _validate_transition(current["status"], new_status):
            return {
                "ok": False,
                "error_code": "illegal_transition",
                "message": f"Cannot transition from {current['status']} to {new_status}",
            }

        now = _now_iso()
        await self.conn.execute(
            "UPDATE applications SET status = ?, last_updated_at = ? WHERE application_id = ?",
            (new_status, now, application_id),
        )
        await self.conn.commit()

        result = await self.get_application(application_id)
        return result if result is not None else {}

    async def append_note(self, application_id: str, content: str) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        current = await self.get_application(application_id)
        if not current:
            return {"ok": False, "error_code": "not_found", "message": f"Application {application_id} not found"}

        import json
        notes = list(current.get("notes") or [])
        note_id = f"note_{uuid.uuid4().hex[:8]}"
        notes.append({
            "note_id": note_id,
            "content": content,
            "created_at": _now_iso(),
        })

        now = _now_iso()
        await self.conn.execute(
            "UPDATE applications SET notes_json = ?, last_updated_at = ? WHERE application_id = ?",
            (json.dumps(notes, ensure_ascii=False), now, application_id),
        )
        await self.conn.commit()

        result = await self.get_application(application_id)
        return result if result is not None else {}

    async def get_application(self, application_id: str) -> dict[str, Any] | None:
        if not self.conn:
            await self.initialize()

        cursor = await self.conn.execute(
            "SELECT * FROM applications WHERE application_id = ?",
            (application_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {}

        return self._row_to_dict(row)

    async def list_applications(
        self,
        candidate_id: str = "",
        status_filter: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self.conn:
            await self.initialize()

        query = "SELECT * FROM applications WHERE 1=1"
        params: list[Any] = []

        if candidate_id:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY last_updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self.conn.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        import json
        d = dict(row)
        try:
            d["notes"] = json.loads(d.get("notes_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["notes"] = []
        d.pop("notes_json", None)
        return d


async def run_application_store(state: dict[str, Any]) -> dict[str, Any]:
    """ApplicationStore Tool node — dispatches CRUD operations.

    Input from state:
        application_store_request: dict with {operation, payload}

    Returns:
        Updates to application_store_response in state.
    """
    from api.core.contracts import ApplicationStoreRequest

    request_raw = state.get("application_store_request") or {}
    try:
        request = ApplicationStoreRequest(**request_raw)
    except Exception:
        return {
            "application_store_response": {
                "ok": False,
                "error_code": "invalid_request",
                "message": "Invalid application store request format",
            },
        }

    store = ApplicationStore()
    await store.initialize()

    try:
        payload = request.payload
        if request.operation == "create_application":
            result = await store.create_application(
                candidate_id=str(payload.get("candidate_id", "")),
                job_id=str(payload.get("job_id", "")),
                company=str(payload.get("company", "")),
                role=str(payload.get("role", "")),
                status=str(payload.get("status", "draft")),
            )
        elif request.operation == "update_status":
            result = await store.update_status(
                application_id=str(payload.get("application_id", "")),
                new_status=str(payload.get("status", "")),
            )
        elif request.operation == "append_note":
            result = await store.append_note(
                application_id=str(payload.get("application_id", "")),
                content=str(payload.get("content", "")),
            )
        elif request.operation == "get_application":
            result = await store.get_application(
                application_id=str(payload.get("application_id", "")),
            )
            if not result:
                return {
                    "application_store_response": {
                        "ok": False,
                        "error_code": "not_found",
                        "message": f"Application {payload.get('application_id', '')} not found",
                    },
                }
            return {
                "application_store_response": {
                    "ok": True,
                    "application_record": result,
                },
            }
        elif request.operation == "list_applications":
            results = await store.list_applications(
                candidate_id=str(payload.get("candidate_id", "")),
                status_filter=str(payload.get("status", "")),
            )
            return {
                "application_store_response": {
                    "ok": True,
                    "application_records": results,
                    "message": f"Found {len(results)} applications",
                },
            }
        else:
            return {
                "application_store_response": {
                    "ok": False,
                    "error_code": "unknown_operation",
                    "message": f"Unknown operation: {request.operation}",
                },
            }

        if isinstance(result, dict) and result.get("error_code"):
            return {
                "application_store_response": {
                    "ok": False,
                    "error_code": result.get("error_code", ""),
                    "message": result.get("message", ""),
                    "application_record": result if request.operation == "create_application" else None,
                },
            }

        return {
            "application_store_response": {
                "ok": True,
                "application_record": result,
            },
        }
    finally:
        await store.close()
