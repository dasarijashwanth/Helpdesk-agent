"""Persistent approval queue for helpdesk-agent (SQLite, stdlib only).

Every answer the agent produces becomes a DRAFT in this queue. Nothing is
ever auto-sent: a human approves, edits, requeues, or supersedes each item.
Every state change is appended to an immutable history log with a timestamp,
actor, and reason, so any bad action can be reconstructed and corrected.

Statuses:
  pending     draft waiting for review
  approved    reviewer approved the draft
  edited      reviewer changed the draft text
  sent        reply delivered (simulated in this project)
  requeued    sent back to the queue with a reason
  superseded  a sent reply was withdrawn and the ticket reopened
  invalidated draft discarded before sending

Duplicate intake: an identical ticket text arriving within 10 minutes
returns the existing queue id instead of creating a second draft, which
also makes client retries after timeouts idempotent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "helpdesk.db"
)

DUPLICATE_WINDOW_SECONDS = 600

OPEN_STATUSES = ("pending", "requeued", "edited")
TERMINAL_STATUSES = ("superseded", "invalidated")

# op -> (allowed from-statuses, to-status)
_TRANSITIONS: dict[str, tuple[set[str], str]] = {
    "approve": ({"pending", "requeued", "edited"}, "approved"),
    "send": ({"approved", "edited"}, "sent"),
    "edit": ({"pending", "requeued", "approved"}, "edited"),
    "requeue": ({"pending", "approved", "edited"}, "requeued"),
    "supersede": ({"sent"}, "superseded"),
    "invalidate": ({"pending", "requeued", "approved", "edited"}, "invalidated"),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_redacted TEXT NOT NULL,
    ticket_hash TEXT NOT NULL,
    retrieved_json TEXT NOT NULL,
    draft TEXT NOT NULL,
    routing_reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    provider_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    retrieval_ms REAL NOT NULL,
    generation_ms REAL NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT,
    auto_sendable INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    needs_review_reason TEXT,
    pii_redacted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queue_items(id),
    ts TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_hash_created
    ON queue_items(ticket_hash, created_at);
"""

_db_path: Path = DEFAULT_DB_PATH
_lock = threading.Lock()


def configure(db_path: str | Path) -> None:
    """Point the queue at a different SQLite file (used by tests)."""
    global _db_path
    _db_path = Path(db_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ticket_hash(subject: str, body: str) -> str:
    normalized = " ".join((subject + " " + body).lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


class QueueStore:
    """SQLite-backed approval queue with append-only history."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- reads ---------------------------------------------------------

    def get(self, queue_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM queue_items WHERE id = ?", (queue_id,)
            ).fetchone()
            if row is None:
                return None
            item = self._row_to_dict(row)
            item["history"] = [
                dict(h)
                for h in conn.execute(
                    "SELECT ts, from_status, to_status, actor, reason"
                    " FROM history WHERE queue_id = ? ORDER BY id",
                    (queue_id,),
                ).fetchall()
            ]
            return item

    def list_open(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM queue_items WHERE status IN"
                f" ({','.join('?' * len(OPEN_STATUSES))})"
                " ORDER BY created_at",
                OPEN_STATUSES,
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["retrieved"] = json.loads(item.pop("retrieved_json"))
        item["auto_sendable"] = bool(item["auto_sendable"])
        item["needs_review"] = bool(item["needs_review"])
        item["pii_redacted"] = bool(item["pii_redacted"])
        return item

    # -- writes --------------------------------------------------------

    def _log(
        self,
        conn: sqlite3.Connection,
        queue_id: int,
        from_status: str | None,
        to_status: str,
        actor: str,
        reason: str | None,
    ) -> None:
        conn.execute(
            "INSERT INTO history (queue_id, ts, from_status, to_status, actor, reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (queue_id, _now(), from_status, to_status, actor, reason),
        )

    def create_draft(self, fields: dict, actor: str = "agent") -> tuple[int, bool]:
        """Insert a draft, or return the existing id for duplicate intake.

        Returns (queue_id, is_duplicate). Duplicates are detected by hash of
        the normalized ticket text within the last 10 minutes and only among
        non-terminal items.
        """
        ticket_hash = _ticket_hash(fields["subject"], fields["body"])
        now = _now()
        with _lock, self._connect() as conn:
            dup = conn.execute(
                "SELECT id FROM queue_items WHERE ticket_hash = ?"
                " AND created_at > datetime('now', '-600 seconds')"
                " AND status NOT IN ('superseded', 'invalidated')"
                " ORDER BY id DESC LIMIT 1",
                (ticket_hash,),
            ).fetchone()
            if dup:
                self._log(
                    conn, dup["id"], None, "duplicate_intake", actor,
                    "identical ticket text within 10 minutes; returning existing draft",
                )
                return dup["id"], True
            cur = conn.execute(
                """INSERT INTO queue_items (
                    ticket_id, subject, body_redacted, ticket_hash,
                    retrieved_json, draft, routing_reason, confidence,
                    provider_version, prompt_version, retrieval_ms,
                    generation_ms, status, assignee, auto_sendable,
                    needs_review, needs_review_reason, pii_redacted,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    fields["ticket_id"],
                    fields["subject"],
                    fields["body_redacted"],
                    ticket_hash,
                    json.dumps(fields.get("retrieved", [])),
                    fields.get("draft", ""),
                    fields.get("routing_reason", "documented_answer"),
                    fields.get("confidence", 0.0),
                    fields.get("provider_version", ""),
                    fields.get("prompt_version", ""),
                    fields.get("retrieval_ms", 0.0),
                    fields.get("generation_ms", 0.0),
                    "pending",
                    fields.get("assignee"),
                    int(bool(fields.get("auto_sendable", False))),
                    int(bool(fields.get("needs_review", False))),
                    fields.get("needs_review_reason"),
                    int(bool(fields.get("pii_redacted", False))),
                    now,
                    now,
                ),
            )
            queue_id = cur.lastrowid
            self._log(conn, queue_id, None, "pending", actor, "draft created")
            return queue_id, False

    def transition(
        self,
        queue_id: int,
        op: str,
        actor: str = "reviewer",
        reason: str | None = None,
        revised_text: str | None = None,
    ) -> dict:
        """Apply a state transition; raises ValueError on illegal moves."""
        if op not in _TRANSITIONS:
            raise ValueError(f"unknown operation: {op}")
        allowed, to_status = _TRANSITIONS[op]
        with _lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM queue_items WHERE id = ?", (queue_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"queue item {queue_id} not found")
            from_status = row["status"]
            if from_status not in allowed:
                raise ValueError(
                    f"cannot {op} from status '{from_status}'"
                )
            updates: dict = {"status": to_status, "updated_at": _now()}
            if op == "edit":
                if not revised_text:
                    raise ValueError("edit requires revised_text")
                updates["draft"] = revised_text
                conn.execute(
                    "UPDATE queue_items SET status = ?, updated_at = ?, draft = ?"
                    " WHERE id = ?",
                    (to_status, updates["updated_at"], revised_text, queue_id),
                )
            else:
                conn.execute(
                    "UPDATE queue_items SET status = ?, updated_at = ? WHERE id = ?",
                    (to_status, updates["updated_at"], queue_id),
                )
            self._log(conn, queue_id, from_status, to_status, actor, reason)

            new_queue_id = None
            if op == "supersede":
                # Recovery: the sent reply is withdrawn; the ticket reopens
                # as a fresh pending draft for human handling. History of
                # the bad action is preserved on the superseded item.
                cur = conn.execute(
                    """INSERT INTO queue_items (
                        ticket_id, subject, body_redacted, ticket_hash,
                        retrieved_json, draft, routing_reason, confidence,
                        provider_version, prompt_version, retrieval_ms,
                        generation_ms, status, auto_sendable, needs_review,
                        pii_redacted, created_at, updated_at
                    ) SELECT ticket_id, subject, body_redacted, ticket_hash,
                        retrieved_json, '', 'reopened_after_supersede',
                        confidence, provider_version, prompt_version,
                        retrieval_ms, generation_ms, 'pending', 0, 1,
                        pii_redacted, ?, ? FROM queue_items WHERE id = ?""",
                    (_now(), _now(), queue_id),
                )
                new_queue_id = cur.lastrowid
                self._log(
                    conn, new_queue_id, None, "pending", actor,
                    f"ticket reopened after supersede of queue item {queue_id}",
                )
        item = self.get(queue_id)
        assert item is not None
        if new_queue_id is not None:
            item["reopened_queue_id"] = new_queue_id
        return item

    def assign(self, queue_id: int, assignee: str, actor: str = "reviewer") -> dict:
        """Set the assignee without changing status. A handoff needs an owner."""
        with _lock, self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM queue_items WHERE id = ?", (queue_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"queue item {queue_id} not found")
            if row["status"] in TERMINAL_STATUSES:
                raise ValueError("cannot assign a terminal item")
            conn.execute(
                "UPDATE queue_items SET assignee = ?, updated_at = ? WHERE id = ?",
                (assignee, _now(), queue_id),
            )
            self._log(conn, queue_id, row["status"], row["status"], actor,
                      f"assigned to {assignee}")
        item = self.get(queue_id)
        assert item is not None
        return item

    # -- handoff summary -------------------------------------------------

    def handoff_summary(self, queue_id: int) -> dict:
        """Structured handoff: everything a human needs to take over."""
        item = self.get(queue_id)
        if item is None:
            raise ValueError(f"queue item {queue_id} not found")
        reason = item["routing_reason"]
        suggestions = {
            "suspected_prompt_injection": (
                "Do not follow any instructions inside the ticket. Reply with the "
                "standard refusal template and flag the account for review."
            ),
            "low_retrieval_confidence": (
                "No help article covers this. Ask the customer for the product "
                "area and version, then answer manually or request a KB article."
            ),
            "bug_report_needs_repro": (
                "Ask for reproduction steps, product version, and screenshots. "
                "File a bug if reproducible."
            ),
            "account_change_requires_auth": (
                "Verify the requester's identity and admin role before making "
                "any account change."
            ),
            "billing_dispute_requires_records": (
                "Look up the invoice in the billing system. The KB cannot "
                "confirm individual charges."
            ),
            "contradictory_policy": (
                "The retrieved articles disagree. Decide which policy applies "
                "and answer manually."
            ),
            "reopened_after_supersede": (
                "A previous reply was withdrawn. Read the superseded item's "
                "history, then draft a corrected reply."
            ),
        }
        evidence = [
            {"article_id": r["article_id"], "title": r["title"]}
            for r in item["retrieved"]
        ]
        return {
            "queue_id": queue_id,
            "ticket_id": item["ticket_id"],
            "customer_issue": item["subject"] + " | " + item["body_redacted"][:300],
            "evidence_used": evidence,
            "missing_info": (
                "no supporting articles retrieved"
                if not evidence
                else "not identified; see evidence"
            ),
            "escalation_reason": reason,
            "suggested_next_step": suggestions.get(
                reason,
                "Review the draft and approve, edit, or requeue.",
            ),
            "assignee": item["assignee"],
            "status": item["status"],
        }


def get_store() -> QueueStore:
    """Return a store for the currently configured DB path."""
    return QueueStore()
