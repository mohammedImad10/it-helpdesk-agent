from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import MEMORY_PATH
from app.models import PendingAction, TicketDraft


@dataclass
class StoredAction:
    action: PendingAction
    draft: TicketDraft
    consumed: bool = False


@dataclass
class Session:
    email: str | None = None
    issue: dict[str, object] = field(default_factory=dict)
    awaiting: str | None = None
    actions: dict[str, StoredAction] = field(default_factory=dict)


class SessionStore:
    """SQLite-backed short-term sessions and requester memory across app restarts."""

    def __init__(self, path: Path = MEMORY_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, email TEXT, issue_json TEXT NOT NULL,
                awaiting TEXT, updated_at TEXT NOT NULL
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS pending_actions (
                action_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, action_json TEXT NOT NULL,
                draft_json TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS requester_memory (
                email TEXT PRIMARY KEY, summary TEXT NOT NULL, last_ticket_id TEXT, updated_at TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def get(self, session_id: str) -> Session:
        row = self.connection.execute(
            "SELECT email, issue_json, awaiting FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return Session()
        actions: dict[str, StoredAction] = {}
        for action_row in self.connection.execute(
            "SELECT action_json, draft_json, consumed FROM pending_actions WHERE session_id = ?", (session_id,)
        ):
            action = PendingAction.model_validate_json(action_row[0])
            actions[action.action_id] = StoredAction(
                action=action, draft=TicketDraft.model_validate_json(action_row[1]), consumed=bool(action_row[2])
            )
        return Session(email=row[0], issue=json.loads(row[1]), awaiting=row[2], actions=actions)

    def save(self, session_id: str, session: Session) -> None:
        self.connection.execute(
            """INSERT INTO sessions(session_id, email, issue_json, awaiting, updated_at)
               VALUES(?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET email=excluded.email, issue_json=excluded.issue_json,
               awaiting=excluded.awaiting, updated_at=excluded.updated_at""",
            (session_id, session.email, json.dumps(session.issue), session.awaiting, self._now()),
        )
        self.connection.commit()

    def put_action(self, session_id: str, stored: StoredAction) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO pending_actions(action_id, session_id, action_json, draft_json, consumed)
               VALUES(?, ?, ?, ?, ?)""",
            (
                stored.action.action_id,
                session_id,
                stored.action.model_dump_json(),
                stored.draft.model_dump_json(),
                int(stored.consumed),
            ),
        )
        self.connection.commit()

    def get_action(self, session_id: str, action_id: str) -> StoredAction | None:
        row = self.connection.execute(
            """SELECT action_json, draft_json, consumed FROM pending_actions
               WHERE session_id = ? AND action_id = ?""",
            (session_id, action_id),
        ).fetchone()
        if row is None:
            return None
        return StoredAction(
            action=PendingAction.model_validate_json(row[0]),
            draft=TicketDraft.model_validate_json(row[1]),
            consumed=bool(row[2]),
        )

    def consume_action(self, action_id: str) -> None:
        self.connection.execute("UPDATE pending_actions SET consumed = 1 WHERE action_id = ?", (action_id,))
        self.connection.commit()

    def remember(self, email: str, summary: str, ticket_id: str | None = None) -> None:
        self.connection.execute(
            """INSERT INTO requester_memory(email, summary, last_ticket_id, updated_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(email) DO UPDATE SET summary=excluded.summary,
               last_ticket_id=COALESCE(excluded.last_ticket_id, requester_memory.last_ticket_id),
               updated_at=excluded.updated_at""",
            (email, summary, ticket_id, self._now()),
        )
        self.connection.commit()

    def memory_for(self, email: str) -> tuple[str, str | None] | None:
        return self.connection.execute(
            "SELECT summary, last_ticket_id FROM requester_memory WHERE email = ?", (email,)
        ).fetchone()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


sessions = SessionStore()
