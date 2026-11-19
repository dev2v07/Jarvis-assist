"""Persistent chat primitives for Jarvis.

The store is intentionally independent from Crazy Tad's database and from the
agent bus. It keeps the transport contract small while leaving the existing
planner/executor/critic pipeline as the only agent orchestrator.
"""

from __future__ import annotations

import json
import mimetypes
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from config import BASE_DIR, STATE_DB_PATH, UPLOAD_DIR


class ChatStore:
    def __init__(self, db_path: str | Path = STATE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _content_with_emote_markers(content: str, attachments: list[dict[str, Any]]) -> str:
        """Keep one U+FFFC slot for every semantic inline emote.

        Older Jarvis drafts were serialized by Qt without image-object
        markers, leaving valid cached GIFs invisible to the source-faithful
        chat renderer.  Repair the returned representation without rewriting
        the stored text; new drafts already carry the markers from the native
        composer.
        """
        value = str(content or "")
        emote_count = sum(
            1 for item in attachments
            if isinstance(item, dict) and isinstance(item.get("emote"), dict)
        )
        missing = emote_count - value.count("\ufffc")
        return value + ("\ufffc" * missing if missing > 0 else "")

    def _init_db(self):
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL DEFAULT 'default',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    attachments_json TEXT NOT NULL DEFAULT '[]',
                    reply_to TEXT,
                    source TEXT NOT NULL DEFAULT 'chat',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'Новый чат',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chat_session_modes (
                    chat_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chat_reactions (
                    message_id TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, reaction, actor),
                    FOREIGN KEY(message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chat_pins (
                    message_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chat_attachments (
                    attachment_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    size INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_time
                    ON chat_messages(chat_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_chat_attachments_message
                    ON chat_attachments(message_id);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO chat_sessions(id, title) VALUES('default', 'JARVIS CHAT')"
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)").fetchall()}
            if "archived" not in columns:
                conn.execute("ALTER TABLE chat_sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            message_columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
            if "source" not in message_columns:
                conn.execute("ALTER TABLE chat_messages ADD COLUMN source TEXT NOT NULL DEFAULT 'chat'")

    def create_session(self, title: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
        session_id = str(chat_id or uuid.uuid4())
        safe_title = str(title or "Новый чат").strip()[:120] or "Новый чат"
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_sessions(id, title) VALUES(?, ?)",
                (session_id, safe_title),
            )
        return self.get_session(session_id) or {}

    def get_session(self, chat_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT sessions.*, modes.mode AS mode
                   FROM chat_sessions AS sessions
                   LEFT JOIN chat_session_modes AS modes ON modes.chat_id=sessions.id
                   WHERE sessions.id=?""",
                (str(chat_id),),
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, include_archived: bool = False) -> list[dict[str, Any]]:
        archive_clause = "1=1" if include_archived else "sessions.archived=0"
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT sessions.*, modes.mode AS mode
                FROM chat_sessions AS sessions
                LEFT JOIN chat_session_modes AS modes ON modes.chat_id=sessions.id
                WHERE {archive_clause}
                  AND (
                      id='default'
                      OR EXISTS (
                          SELECT 1 FROM chat_messages
                          WHERE chat_messages.chat_id=sessions.id
                      )
                  )
                ORDER BY pinned DESC, updated_at DESC, created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session_mode(self, chat_id: str) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT mode FROM chat_session_modes WHERE chat_id=?", (str(chat_id),)
            ).fetchone()
        return str(row["mode"]) if row and row["mode"] else None

    def set_session_mode(self, chat_id: str, mode: str | None) -> dict[str, Any] | None:
        session_id = str(chat_id)
        normalized = str(mode or "").strip().upper() or None
        with self._lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM chat_sessions WHERE id=?", (session_id,)).fetchone():
                return None
            if normalized is None:
                conn.execute("DELETE FROM chat_session_modes WHERE chat_id=?", (session_id,))
            else:
                conn.execute(
                    """INSERT INTO chat_session_modes(chat_id, mode, updated_at)
                       VALUES(?,?,CURRENT_TIMESTAMP)
                       ON CONFLICT(chat_id) DO UPDATE SET mode=excluded.mode,
                       updated_at=CURRENT_TIMESTAMP""",
                    (session_id, normalized),
                )
        return self.get_session(session_id)

    def bind_session_mode_by_title(self, title: str, mode: str) -> dict[str, Any] | None:
        needle = " ".join(str(title or "").casefold().replace("ё", "е").split())
        if not needle:
            return None
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT id, title, updated_at, created_at FROM chat_sessions
                   WHERE archived=0 ORDER BY updated_at DESC, created_at DESC""",
            ).fetchall()
            rows = [
                row for row in rows
                if " ".join(str(row["title"] or "").casefold().replace("ё", "е").split()) == needle
            ]
            if not rows:
                return None
            # Bind the already existing, most recently used exact-title chat.
            # The mode is stored by ID and survives future renames.
            chat_id = str(rows[0]["id"])
            conn.execute(
                """INSERT INTO chat_session_modes(chat_id, mode, updated_at)
                   VALUES(?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(chat_id) DO UPDATE SET mode=excluded.mode,
                   updated_at=CURRENT_TIMESTAMP""",
                (chat_id, str(mode).strip().upper()),
            )
        return self.get_session(chat_id)

    def rename_session(self, chat_id: str, title: str) -> dict[str, Any] | None:
        safe_title = str(title or "Новый чат").strip()[:120] or "Новый чат"
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE chat_sessions SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (safe_title, str(chat_id)))
        return self.get_session(chat_id)

    def toggle_session_pin(self, chat_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT pinned FROM chat_sessions WHERE id=?", (str(chat_id),)).fetchone()
            if not row:
                return None
            pinned = not bool(row["pinned"])
            if pinned:
                pinned_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM chat_sessions AS sessions
                    WHERE sessions.pinned=1 AND sessions.archived=0
                      AND (
                          sessions.id='default'
                          OR EXISTS (
                              SELECT 1 FROM chat_messages
                              WHERE chat_messages.chat_id=sessions.id
                          )
                      )
                    """
                ).fetchone()[0]
                if pinned_count >= 4:
                    raise ValueError("Maximum of 4 pinned chats reached")
            conn.execute("UPDATE chat_sessions SET pinned=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(pinned), str(chat_id)))
        return self.get_session(chat_id)

    def archive_session(self, chat_id: str) -> dict[str, Any] | None:
        if str(chat_id) == "default":
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT archived FROM chat_sessions WHERE id=?", (str(chat_id),)).fetchone()
            if not row:
                return None
            archived = not bool(row["archived"])
            conn.execute(
                "UPDATE chat_sessions SET archived=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(archived), str(chat_id)),
            )
        return self.get_session(chat_id)

    def delete_session(self, chat_id: str) -> bool:
        if str(chat_id) == "default":
            return False
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT 1 FROM chat_sessions WHERE id=?", (str(chat_id),)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM chat_messages WHERE chat_id=?", (str(chat_id),))
            conn.execute("DELETE FROM chat_session_modes WHERE chat_id=?", (str(chat_id),))
            conn.execute("DELETE FROM chat_sessions WHERE id=?", (str(chat_id),))
        return True

    def touch_session(self, chat_id: str, title: str | None = None) -> None:
        session_id = str(chat_id or "default")
        safe_title = str(title or "").strip()[:120]
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO chat_sessions(id, title) VALUES(?, 'Новый чат')",
                (session_id,),
            )
            if safe_title:
                conn.execute(
                    "UPDATE chat_sessions SET title=? WHERE id=? AND title='Новый чат'",
                    (safe_title, session_id),
                )
            conn.execute("UPDATE chat_sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))

    def delete_message(self, message_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT 1 FROM chat_messages WHERE id=?", (str(message_id),)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM chat_messages WHERE id=?", (str(message_id),))
        return True

    def clear_history(self, chat_id: str) -> bool:
        """Delete all messages and cached attachment rows for one chat."""
        session_id = str(chat_id or "default")
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT 1 FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                return False
            attachment_rows = conn.execute(
                "SELECT stored_path FROM chat_attachments WHERE message_id IN "
                "(SELECT id FROM chat_messages WHERE chat_id=?)",
                (session_id,),
            ).fetchall()
            conn.execute(
                "DELETE FROM chat_attachments WHERE message_id IN "
                "(SELECT id FROM chat_messages WHERE chat_id=?)",
                (session_id,),
            )
            conn.execute("DELETE FROM chat_messages WHERE chat_id=?", (session_id,))
        for row in attachment_rows:
            try:
                Path(str(row["stored_path"])).unlink(missing_ok=True)
            except OSError:
                pass
        return True

    @staticmethod
    def _safe_source(path_value: str | Path) -> Path | None:
        """Resolve a user-selected file without allowing arbitrary serving."""
        try:
            candidate = Path(path_value).expanduser().resolve()
        except (TypeError, ValueError, OSError):
            return None
        if not candidate.is_file():
            return None
        # The source may be a project asset or a user file selected in the
        # native picker. It is copied into UPLOAD_DIR before it is served.
        return candidate

    def register_attachments(
        self,
        attachments: list[dict[str, Any]] | None,
        *,
        message_id: str,
    ) -> list[dict[str, Any]]:
        """Cache draft files and return transport-safe media descriptors."""
        normalized: list[dict[str, Any]] = []
        media_root = UPLOAD_DIR / "chat-media"
        media_root.mkdir(parents=True, exist_ok=True)
        for raw in (attachments or [])[:12]:
            if not isinstance(raw, dict):
                continue
            # Reply metadata is carried in the same draft list by the donor
            # composer but is not a file and must remain untouched.
            if raw.get("reply_to") and not raw.get("path"):
                normalized.append({"reply_to": raw["reply_to"]})
                continue
            source = self._safe_source(raw.get("path") or raw.get("cached_path") or "")
            if source is None:
                # Keep semantic descriptors visible to the UI, but never keep
                # an arbitrary path that could become a file:// escape hatch.
                safe = {
                    key: str(raw[key])[:180]
                    for key in ("name", "kind", "pack_id", "item_id", "send_mode")
                    if raw.get(key) is not None
                }
                if safe.get("name"):
                    normalized.append(safe)
                continue
            attachment_id = "att_" + uuid.uuid4().hex
            suffix = source.suffix[:16]
            destination = media_root / f"{attachment_id}{suffix}"
            try:
                shutil.copy2(source, destination)
                size = destination.stat().st_size
            except OSError:
                continue
            media_type = str(raw.get("media_type") or mimetypes.guess_type(source.name)[0] or "application/octet-stream")
            descriptor = {
                "attachment_id": attachment_id,
                "name": str(raw.get("name") or source.name)[:180],
                "media_type": media_type,
                "type": media_type.split("/", 1)[0],
                "kind": str(raw.get("kind") or "file")[:40],
                "pack_id": str(raw.get("pack_id") or "")[:80],
                "item_id": str(raw.get("item_id") or "")[:120],
                "send_mode": str(raw.get("send_mode") or "file")[:40],
                "size": size,
            }
            if isinstance(raw.get("emote"), dict):
                descriptor["emote"] = {
                    key: str(raw["emote"][key])[:180]
                    for key in ("pack_id", "item_id", "kind", "send_mode", "name", "title", "fallback")
                    if raw["emote"].get(key) is not None
                }
            elif str(raw.get("pack_id") or "") in {"mailru_agent", "telegram_retro"}:
                descriptor["emote"] = {
                    key: str(raw[key])[:180]
                    for key in ("pack_id", "item_id", "kind", "send_mode")
                    if raw.get(key) is not None
                }
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO chat_attachments(attachment_id, message_id, original_name, stored_path, media_type, size) VALUES(?,?,?,?,?,?)",
                    (attachment_id, message_id, descriptor["name"], str(destination), media_type, size),
                )
            normalized.append(descriptor)
        return normalized

    def attachment_path(self, attachment_id: str) -> tuple[Path, str, str] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT stored_path, original_name, media_type FROM chat_attachments WHERE attachment_id=?",
                (str(attachment_id),),
            ).fetchone()
        if not row:
            return None
        try:
            path = Path(row["stored_path"]).resolve()
            path.relative_to(UPLOAD_DIR.resolve())
        except (OSError, ValueError):
            return None
        return path, str(row["original_name"]), str(row["media_type"])

    def add_message(
        self,
        *,
        chat_id: str,
        role: str,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
        reply_to: str | None = None,
        message_id: str | None = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        message_id = message_id or "msg_" + uuid.uuid4().hex
        safe_attachments = [item for item in (attachments or []) if isinstance(item, dict)]
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages(id, chat_id, role, content, attachments_json, reply_to, source) VALUES(?,?,?,?,?,?,?)",
                (message_id, str(chat_id or "default"), str(role), str(content or ""),
                 json.dumps(safe_attachments, ensure_ascii=False), reply_to,
                 str(source or "chat").strip().lower()[:24] or "chat"),
            )
        return self.get_message(message_id) or {}

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
        return self._row(row) if row else None

    def replace_message_attachments(self, message_id: str, attachments: list[dict[str, Any]]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE chat_messages SET attachments_json=? WHERE id=?",
                (json.dumps(attachments, ensure_ascii=False), str(message_id)),
            )

    def list_messages(
        self,
        chat_id: str = "default",
        limit: int = 100,
        *,
        after_id: str | None = None,
        before_id: str | None = None,
        ids: list[str] | None = None,
        latest: bool = False,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock, self._connect() as conn:
            params: list[Any] = [str(chat_id or "default")]
            clauses = ["chat_id=?"]
            if source:
                clauses.append("source=?")
                params.append(str(source).strip().lower())
            if ids:
                placeholders = ",".join("?" for _ in ids[:500])
                clauses.append(f"id IN ({placeholders})")
                params.extend(str(value) for value in ids[:500])
            query = "SELECT * FROM chat_messages WHERE " + " AND ".join(clauses)
            if after_id:
                query += " AND rowid > COALESCE((SELECT rowid FROM chat_messages WHERE id=?), 0)"
                params.append(str(after_id))
            if before_id:
                query += " AND rowid < COALESCE((SELECT rowid FROM chat_messages WHERE id=?), 9223372036854775807)"
                params.append(str(before_id))
            if latest and not after_id and not before_id and not ids:
                query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
            else:
                query += " ORDER BY created_at, rowid LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        if latest and not after_id and not before_id and not ids:
            rows.reverse()
        return [self._row(row) for row in rows]

    def toggle_reaction(self, message_id: str, reaction: str, actor: str = "user") -> dict[str, Any]:
        reaction = str(reaction or "").strip()[:16]
        if not reaction:
            raise ValueError("reaction is required")
        with self._lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM chat_reactions WHERE message_id=? AND reaction=? AND actor=?",
                (message_id, reaction, actor),
            ).fetchone()
            if exists:
                conn.execute(
                    "DELETE FROM chat_reactions WHERE message_id=? AND reaction=? AND actor=?",
                    (message_id, reaction, actor),
                )
                active = False
            else:
                conn.execute(
                    "INSERT INTO chat_reactions(message_id, reaction, actor) VALUES(?,?,?)",
                    (message_id, reaction, actor),
                )
                active = True
        return {"message_id": message_id, "reaction": reaction, "active": active}

    def toggle_pin(self, message_id: str, actor: str = "user") -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM chat_pins WHERE message_id=?", (message_id,)).fetchone()
            if exists:
                conn.execute("DELETE FROM chat_pins WHERE message_id=?", (message_id,))
                pinned = False
            else:
                conn.execute("INSERT INTO chat_pins(message_id, actor) VALUES(?,?)", (message_id, actor))
                pinned = True
        return {"message_id": message_id, "pinned": pinned}

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            attachments = json.loads(row["attachments_json"] or "[]")
        except (TypeError, ValueError):
            attachments = []
        with self._lock, self._connect() as conn:
            reactions = [dict(item) for item in conn.execute(
                "SELECT reaction, actor FROM chat_reactions WHERE message_id=? ORDER BY created_at",
                (row["id"],),
            ).fetchall()]
            pinned = bool(conn.execute("SELECT 1 FROM chat_pins WHERE message_id=?", (row["id"],)).fetchone())
        if any(
            isinstance(item, dict)
            and item.get("path")
            and not item.get("attachment_id")
            for item in attachments
        ):
            # Migrate pre-media-cache messages lazily. This keeps old chat
            # history playable without requiring a destructive DB migration.
            migrated = self.register_attachments(attachments, message_id=str(row["id"]))
            self.replace_message_attachments(str(row["id"]), migrated)
            attachments = migrated
        content = self._content_with_emote_markers(row["content"], attachments)
        return {
            "id": row["id"], "chat_id": row["chat_id"], "role": row["role"],
            "content": content, "attachments": attachments,
            "source": str(row["source"] or "chat") if "source" in row.keys() else "chat",
            "reply_to": row["reply_to"], "created_at": row["created_at"],
            "reactions": reactions, "pinned": pinned, "is_pinned": pinned,
        }

