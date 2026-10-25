from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from config import REQUEST_HISTORY_LIMIT, STATE_DB_PATH


class SQLiteStateStore:

    def __init__(self, db_path: str | Path = STATE_DB_PATH):

        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()

        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False
        )

        self._conn.row_factory = sqlite3.Row

        self._init_db()

    # --------------------------------------------------
    # INIT DATABASE
    # --------------------------------------------------

    def _init_db(self):

        with self._conn:

            self._conn.execute("PRAGMA journal_mode=WAL")

            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    events_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    current_step TEXT,
                    completed_steps_json TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    permission_request_json TEXT,
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    # --------------------------------------------------
    # UPSERT REQUEST
    # --------------------------------------------------

    def upsert_request(self, state: dict[str, Any]):

        payload = {

            "request_id": state["request_id"],

            "status": state["status"],

            "goal": state.get("goal", ""),

            "mode": state.get("mode", "general"),

            "events_json": json.dumps(
                state.get("events", []),
                ensure_ascii=False
            ),

            "plan_json": json.dumps(
                state.get("plan", []),
                ensure_ascii=False
            ),

            "current_step": state.get("current_step"),

            "completed_steps_json": json.dumps(
                state.get("completed_steps", []),
                ensure_ascii=False
            ),

            "result": state.get("result"),

            "error": state.get("error"),

            "permission_request_json": (
                json.dumps(state.get("permission_request"))
                if state.get("permission_request") is not None
                else None
            ),

            "artifacts_json": json.dumps(
                state.get("artifacts", []),
                ensure_ascii=False
            ),
        }

        with self._lock, self._conn:

            self._conn.execute(
                """
                INSERT INTO requests (
                    request_id,
                    status,
                    goal,
                    mode,
                    events_json,
                    plan_json,
                    current_step,
                    completed_steps_json,
                    result,
                    error,
                    permission_request_json,
                    artifacts_json,
                    updated_at
                ) VALUES (
                    :request_id,
                    :status,
                    :goal,
                    :mode,
                    :events_json,
                    :plan_json,
                    :current_step,
                    :completed_steps_json,
                    :result,
                    :error,
                    :permission_request_json,
                    :artifacts_json,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(request_id) DO UPDATE SET
                    status=excluded.status,
                    goal=excluded.goal,
                    mode=excluded.mode,
                    events_json=excluded.events_json,
                    plan_json=excluded.plan_json,
                    current_step=excluded.current_step,
                    completed_steps_json=excluded.completed_steps_json,
                    result=excluded.result,
                    error=excluded.error,
                    permission_request_json=excluded.permission_request_json,
                    artifacts_json=excluded.artifacts_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                payload,
            )

    # --------------------------------------------------
    # GET REQUEST
    # --------------------------------------------------

    def get_request(self, request_id: str) -> dict[str, Any] | None:

        with self._lock:

            row = self._conn.execute(
                "SELECT * FROM requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()

        return self._row_to_state(row) if row else None

    # --------------------------------------------------
    # HISTORY
    # --------------------------------------------------

    def list_recent_requests(
        self,
        limit: int = REQUEST_HISTORY_LIMIT
    ) -> list[dict[str, Any]]:

        with self._lock:

            rows = self._conn.execute(
                """
                SELECT *
                FROM requests
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_state(row) for row in rows]

    # --------------------------------------------------
    # ROW PARSER
    # --------------------------------------------------

    def _row_to_state(self, row: sqlite3.Row) -> dict[str, Any]:

        def safe_json(value, default):

            try:

                return json.loads(value)

            except Exception:

                return default

        return {

            "request_id": row["request_id"],

            "status": row["status"],

            "goal": row["goal"],

            "mode": row["mode"],

            "events": safe_json(row["events_json"], []),

            "plan": safe_json(row["plan_json"], []),

            "current_step": row["current_step"],

            "completed_steps": safe_json(
                row["completed_steps_json"],
                []
            ),

            "result": row["result"],

            "error": row["error"],

            "permission_request": safe_json(
                row["permission_request_json"],
                None
            ),

            "artifacts": safe_json(
                row["artifacts_json"],
                [],
            ),
        }

    # --------------------------------------------------
    # CLOSE
    # --------------------------------------------------

    def close(self):

        with self._lock:

            self._conn.close()