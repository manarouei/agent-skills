"""
State Store - Lightweight persistence for agent context and memory.

This module provides state persistence for multi-turn agent interactions:
- conversation_events: Append-only event log (bounded)
- pocket_facts: Structured facts with upsert semantics (avoids bloat)
- conversation_summary: Periodic summary text (bounded)

DESIGN PRINCIPLES:
1. Stdlib only: Uses sqlite3 (no external deps)
2. Bounded: Hard limits on events, facts, summary size
3. Interface-first: Abstract base allows Postgres backend later
4. Sync-safe: No async, works in Celery context
5. Distributed-safe: Pluggable backends via STATE_STORE_BACKEND env var

STORAGE LOCATION:
Default: artifacts/{context_id}/.state.db (per-correlation)
Or: .state/agent_state.db (shared, for cross-correlation queries)
Or: PostgreSQL via STATE_STORE_BACKEND=postgres (production)

RETENTION KNOBS:
- MAX_EVENTS_PER_CONTEXT: 100 (oldest trimmed on insert)
- MAX_POCKET_FACTS_PER_BUCKET: 50 (oldest trimmed on insert)
- MAX_SUMMARY_SIZE_CHARS: 10000 (truncated on update)

CONCURRENCY:
- context_version: Optimistic concurrency via CAS update
- message_id: Dedupe for idempotent event append
- resume_token: Validates state hasn't changed since last read
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# RETENTION LIMITS (hard bounds to prevent bloat)
# =============================================================================

MAX_EVENTS_PER_CONTEXT: int = 100
MAX_POCKET_FACTS_PER_BUCKET: int = 50
MAX_SUMMARY_SIZE_CHARS: int = 10000


# =============================================================================
# STATE PERSISTENCE POLICIES (per-skill configurable)
# =============================================================================

class StatePersistencePolicy(str):
    """Policy for what state to persist."""
    NONE = "none"           # No persistence (stateless tool)
    FACTS_ONLY = "facts_only"  # Only pocket facts (lightweight)
    FULL_EVENTS = "full_events"  # Full event log + facts (audit trail)


DEFAULT_PERSISTENCE_POLICY = StatePersistencePolicy.FACTS_ONLY


# =============================================================================
# REDACTION (privacy/security layer)
# =============================================================================

# Patterns to redact from stored values
REDACTION_PATTERNS: List[Tuple[str, str]] = [
    (r'(?i)(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})', r'\1=***REDACTED***'),
    (r'(?i)(secret|password|token|bearer)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{8,})', r'\1=***REDACTED***'),
    (r'(?i)authorization["\']?\s*[:=]\s*["\']?bearer\s+([a-zA-Z0-9_\-\.]+)', r'Authorization: Bearer ***REDACTED***'),
    # OpenAI-style API keys (sk-..., pk-..., etc.)
    (r'\b(sk|pk|rk)-[a-zA-Z0-9]{16,}\b', r'***REDACTED***'),
]


def redact_sensitive(value: Any) -> Any:
    """
    Redact sensitive data from a value before persistence.
    
    Applies pattern-based redaction to strings and recursively to dicts/lists.
    """
    if isinstance(value, str):
        result = value
        for pattern, replacement in REDACTION_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result
    elif isinstance(value, dict):
        return {k: redact_sensitive(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [redact_sensitive(v) for v in value]
    return value


# =============================================================================
# DATA MODELS
# =============================================================================

class ConversationEvent(BaseModel):
    """Single event in the conversation log."""
    model_config = ConfigDict(extra="forbid")
    
    event_type: str = Field(..., description="Type of event (message, state_change, etc.)")
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    turn_number: int = Field(default=1, ge=1)
    agent_id: Optional[str] = Field(default=None, description="Agent that produced this event")
    message_id: Optional[str] = Field(default=None, description="Unique message ID for dedupe")


class PocketFact(BaseModel):
    """
    Small structured fact for quick retrieval.
    
    Facts are organized by bucket (namespace) and key.
    Upsert semantics: inserting with same bucket+key updates the value.
    """
    model_config = ConfigDict(extra="forbid")
    
    bucket: str = Field(..., description="Namespace (e.g., 'inputs', 'schema', 'errors')")
    key: str = Field(..., description="Fact key within bucket")
    value: Any = Field(..., description="Fact value (JSON-serializable)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: Optional[int] = Field(default=None, description="Time-to-live (None=forever)")


class ConversationSummary(BaseModel):
    """Periodic summary of conversation state."""
    model_config = ConfigDict(extra="forbid")
    
    summary_text: str = Field(..., max_length=MAX_SUMMARY_SIZE_CHARS)
    turn_number: int = Field(..., ge=1, description="Turn at which summary was generated")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ContextState(BaseModel):
    """Complete state snapshot for a context."""
    model_config = ConfigDict(extra="forbid")
    
    context_id: str
    current_turn: int = Field(default=1, ge=1)
    task_state: str = Field(default="pending")
    events: List[ConversationEvent] = Field(default_factory=list)
    facts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # bucket -> key -> value
    summary: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Concurrency control
    version: int = Field(default=1, ge=1, description="Optimistic concurrency version")
    resume_token: Optional[str] = Field(default=None, description="Token for resume validation")
    
    # Metadata for semantic state preservation
    agent_state_detail: Optional[str] = Field(
        default=None, 
        description="Detailed agent state (input_required, delegating, paused)"
    )
    input_request_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured payload when agent_state_detail=input_required"
    )


class VersionConflictError(Exception):
    """Raised when CAS update fails due to version mismatch."""
    def __init__(self, context_id: str, expected: int, actual: int):
        self.context_id = context_id
        self.expected_version = expected
        self.actual_version = actual
        super().__init__(
            f"Version conflict for context {context_id}: "
            f"expected {expected}, actual {actual}"
        )


class DuplicateMessageError(Exception):
    """Raised when attempting to append a duplicate message_id."""
    def __init__(self, context_id: str, message_id: str):
        self.context_id = context_id
        self.message_id = message_id
        super().__init__(f"Duplicate message_id {message_id} for context {context_id}")


# =============================================================================
# ABSTRACT INTERFACE
# =============================================================================

class StateStore(ABC):
    """
    Abstract interface for state persistence.
    
    Implementations:
    - SQLiteStateStore (default, stdlib, dev/single-host)
    - PostgresStateStore (production, multi-worker)
    
    Concurrency:
    - All mutating operations support optimistic concurrency via expected_version
    - append_event supports message_id dedupe
    """
    
    @abstractmethod
    def get_state(self, context_id: str) -> Optional[ContextState]:
        """Get full state for a context, including version."""
        ...
    
    @abstractmethod
    def put_state(
        self, 
        context_id: str, 
        state: ContextState,
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Put full state for a context with optimistic concurrency.
        
        Args:
            context_id: Context identifier
            state: New state to store
            expected_version: If set, CAS update (raises VersionConflictError on mismatch)
        
        Returns:
            New version number
        
        Raises:
            VersionConflictError: If expected_version doesn't match
        """
        ...
    
    @abstractmethod
    def append_event(
        self, 
        context_id: str, 
        event: ConversationEvent,
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Append event to conversation log (bounded, idempotent via message_id).
        
        Args:
            context_id: Context identifier
            event: Event to append
            expected_version: If set, CAS update
        
        Returns:
            New version number
        
        Raises:
            DuplicateMessageError: If event.message_id already exists
            VersionConflictError: If expected_version doesn't match
        """
        ...
    
    @abstractmethod
    def get_events(self, context_id: str, limit: int = 50) -> List[ConversationEvent]:
        """Get recent events for context."""
        ...
    
    @abstractmethod
    def put_fact(
        self, 
        context_id: str, 
        fact: PocketFact,
        redact: bool = True,
    ) -> None:
        """
        Upsert a pocket fact.
        
        Args:
            context_id: Context identifier
            fact: Fact to store
            redact: If True (default), apply redaction before storing
        """
        ...
    
    @abstractmethod
    def get_fact(self, context_id: str, bucket: str, key: str) -> Optional[Any]:
        """Get a specific fact value."""
        ...
    
    @abstractmethod
    def get_facts_by_bucket(self, context_id: str, bucket: str) -> Dict[str, Any]:
        """Get all facts in a bucket."""
        ...
    
    @abstractmethod
    def update_summary(self, context_id: str, summary: ConversationSummary) -> None:
        """Update conversation summary (bounded size)."""
        ...
    
    @abstractmethod
    def get_summary(self, context_id: str) -> Optional[str]:
        """Get current summary text."""
        ...
    
    @abstractmethod
    def update_task_state(
        self, 
        context_id: str, 
        task_state: str, 
        turn: int,
        agent_state_detail: Optional[str] = None,
        input_request_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update task state and turn number with semantic detail.
        
        Args:
            context_id: Context identifier
            task_state: High-level state (pending, completed, blocked, etc.)
            turn: Current turn number
            agent_state_detail: Detailed agent state (input_required, delegating, paused)
            input_request_payload: Structured payload for input requests
        """
        ...
    
    @abstractmethod
    def generate_resume_token(self, context_id: str) -> str:
        """Generate a resume token for the current state."""
        ...
    
    @abstractmethod
    def validate_resume_token(self, context_id: str, token: str) -> bool:
        """Validate a resume token matches current state."""
        ...
    
    @abstractmethod
    def prune_expired(self, context_id: Optional[str] = None) -> int:
        """
        Prune expired facts (TTL) and over-limit events.
        
        Args:
            context_id: If set, prune only this context; otherwise all
        
        Returns:
            Number of items pruned
        """
        ...
    
    @abstractmethod
    def close(self) -> None:
        """Close any resources."""
        ...
    
    # =========================================================================
    # DELEGATION OUTBOX (for agent-to-agent messaging)
    # =========================================================================
    
    @abstractmethod
    def save_outbox_message(
        self,
        context_id: str,
        message_id: str,
        target_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """
        Save a delegation message to the outbox.
        
        Outbox pattern: messages are persisted before acknowledgment,
        enabling reliable delivery without blocking the skill.
        
        Args:
            context_id: Originating context
            message_id: Unique message identifier for deduplication
            target_agent: Target agent identifier
            message_type: Message type (e.g., 'delegate', 'query')
            payload: Message payload (redacted before storage)
            correlation_id: For request-response correlation
        
        Raises:
            DuplicateMessageError: If message_id already exists
        """
        ...
    
    @abstractmethod
    def get_pending_outbox_messages(
        self,
        context_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get pending (undelivered) outbox messages.
        
        Args:
            context_id: Filter by context (None = all)
            limit: Maximum messages to return
        
        Returns:
            List of pending messages with all fields
        """
        ...
    
    @abstractmethod
    def mark_outbox_delivered(
        self,
        message_id: str,
        delivered_at: Optional[str] = None,
    ) -> bool:
        """
        Mark an outbox message as delivered.
        
        Args:
            message_id: Message to mark
            delivered_at: Delivery timestamp (default: now)
        
        Returns:
            True if message was marked, False if not found
        """
        ...
    
    @abstractmethod
    def mark_outbox_failed(
        self,
        message_id: str,
        error: str,
        retry_count: int = 0,
    ) -> bool:
        """
        Mark an outbox message as failed.
        
        Args:
            message_id: Message to mark
            error: Error description
            retry_count: Current retry count
        
        Returns:
            True if message was marked, False if not found
        """
        ...


# =============================================================================
# SQLITE IMPLEMENTATION (dev/single-host)
# =============================================================================

class SQLiteStateStore(StateStore):
    """
    SQLite-backed state store.
    
    Thread-safe via connection-per-thread pattern.
    Uses artifacts/{context_id}/.state.db or shared path.
    
    WARNING: NOT safe for multi-worker Celery deployments.
    Use PostgresStateStore for production.
    """
    
    def __init__(self, db_path: Path | str | None = None, shared: bool = False):
        """
        Initialize SQLite state store.
        
        Args:
            db_path: Explicit path to database file
            shared: If True, use shared .state/agent_state.db
        """
        if db_path:
            self._db_path = Path(db_path)
        elif shared:
            self._db_path = Path(".state") / "agent_state.db"
        else:
            # Per-context mode: db_path determined per operation
            self._db_path = None
        
        # Thread-local connections
        self._local = threading.local()
        
        # Initialize shared DB if specified
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema(self._get_connection())
    
    def _get_db_path(self, context_id: str | None = None) -> Path:
        """Get database path, creating parent dirs if needed."""
        if self._db_path:
            return self._db_path
        if context_id:
            path = Path("artifacts") / context_id / ".state.db"
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        raise ValueError("No db_path and no context_id provided")
    
    def _get_connection(self, context_id: str | None = None) -> sqlite3.Connection:
        """Get thread-local connection."""
        db_path = self._get_db_path(context_id)
        
        # Use db_path as key for connection cache
        cache_key = str(db_path)
        if not hasattr(self._local, "connections"):
            self._local.connections = {}
        
        if cache_key not in self._local.connections:
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._init_schema(conn)
            self._local.connections[cache_key] = conn
        
        return self._local.connections[cache_key]
    
    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize database schema with versioning support."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS context_state (
                context_id TEXT PRIMARY KEY,
                current_turn INTEGER DEFAULT 1,
                task_state TEXT DEFAULT 'pending',
                summary TEXT,
                version INTEGER DEFAULT 1,
                resume_token TEXT,
                agent_state_detail TEXT,
                input_request_payload TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS conversation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                agent_id TEXT,
                message_id TEXT,
                FOREIGN KEY (context_id) REFERENCES context_state(context_id),
                UNIQUE(context_id, message_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_events_context 
                ON conversation_events(context_id, timestamp DESC);
            
            CREATE INDEX IF NOT EXISTS idx_events_message_id
                ON conversation_events(context_id, message_id);
            
            CREATE TABLE IF NOT EXISTS pocket_facts (
                context_id TEXT NOT NULL,
                bucket TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                ttl_seconds INTEGER,
                expires_at TEXT,
                PRIMARY KEY (context_id, bucket, key)
            );
            
            CREATE INDEX IF NOT EXISTS idx_facts_bucket 
                ON pocket_facts(context_id, bucket);
            
            CREATE INDEX IF NOT EXISTS idx_facts_expires
                ON pocket_facts(expires_at) WHERE expires_at IS NOT NULL;
            
            -- Delegation outbox table (agent-to-agent messaging)
            CREATE TABLE IF NOT EXISTS delegation_outbox (
                message_id TEXT PRIMARY KEY,
                context_id TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                message_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                FOREIGN KEY (context_id) REFERENCES context_state(context_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_outbox_status
                ON delegation_outbox(status, created_at);
            
            CREATE INDEX IF NOT EXISTS idx_outbox_context
                ON delegation_outbox(context_id, status);
        """)
        conn.commit()
    
    def _ensure_context(self, conn: sqlite3.Connection, context_id: str) -> int:
        """Ensure context_state row exists, return current version."""
        now = datetime.utcnow().isoformat()
        
        # Try insert
        conn.execute("""
            INSERT OR IGNORE INTO context_state (context_id, version, created_at, updated_at)
            VALUES (?, 1, ?, ?)
        """, (context_id, now, now))
        conn.commit()
        
        # Get current version
        row = conn.execute(
            "SELECT version FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        return row["version"] if row else 1
    
    def _increment_version(self, conn: sqlite3.Connection, context_id: str, expected: Optional[int]) -> int:
        """Increment version with optional CAS check."""
        now = datetime.utcnow().isoformat()
        
        if expected is not None:
            # CAS update
            cursor = conn.execute("""
                UPDATE context_state 
                SET version = version + 1, updated_at = ?
                WHERE context_id = ? AND version = ?
            """, (now, context_id, expected))
            
            if cursor.rowcount == 0:
                # Check if context exists
                row = conn.execute(
                    "SELECT version FROM context_state WHERE context_id = ?",
                    (context_id,)
                ).fetchone()
                actual = row["version"] if row else 0
                raise VersionConflictError(context_id, expected, actual)
        else:
            conn.execute("""
                UPDATE context_state 
                SET version = version + 1, updated_at = ?
                WHERE context_id = ?
            """, (now, context_id))
        
        conn.commit()
        
        # Return new version
        row = conn.execute(
            "SELECT version FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        return row["version"]
    
    def _trim_events(self, conn: sqlite3.Connection, context_id: str) -> None:
        """Trim events to MAX_EVENTS_PER_CONTEXT."""
        conn.execute("""
            DELETE FROM conversation_events
            WHERE context_id = ? AND id NOT IN (
                SELECT id FROM conversation_events
                WHERE context_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        """, (context_id, context_id, MAX_EVENTS_PER_CONTEXT))
        conn.commit()
    
    def _trim_facts(self, conn: sqlite3.Connection, context_id: str, bucket: str) -> None:
        """Trim facts in bucket to MAX_POCKET_FACTS_PER_BUCKET."""
        conn.execute("""
            DELETE FROM pocket_facts
            WHERE context_id = ? AND bucket = ? AND key NOT IN (
                SELECT key FROM pocket_facts
                WHERE context_id = ? AND bucket = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        """, (context_id, bucket, context_id, bucket, MAX_POCKET_FACTS_PER_BUCKET))
        conn.commit()
    
    # === StateStore interface implementation ===
    
    def get_state(self, context_id: str) -> Optional[ContextState]:
        """Get full state for a context, including version."""
        conn = self._get_connection(context_id)
        
        row = conn.execute(
            "SELECT * FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        
        if not row:
            return None
        
        events = self.get_events(context_id, limit=MAX_EVENTS_PER_CONTEXT)
        
        # Build facts dict
        facts: Dict[str, Dict[str, Any]] = {}
        for fact_row in conn.execute(
            "SELECT bucket, key, value FROM pocket_facts WHERE context_id = ?",
            (context_id,)
        ):
            bucket = fact_row["bucket"]
            if bucket not in facts:
                facts[bucket] = {}
            facts[bucket][fact_row["key"]] = json.loads(fact_row["value"])
        
        # Parse input_request_payload if present
        input_request_payload = None
        if row["input_request_payload"]:
            try:
                input_request_payload = json.loads(row["input_request_payload"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return ContextState(
            context_id=context_id,
            current_turn=row["current_turn"],
            task_state=row["task_state"],
            events=events,
            facts=facts,
            summary=row["summary"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            version=row["version"] if "version" in row.keys() else 1,
            resume_token=row["resume_token"] if "resume_token" in row.keys() else None,
            agent_state_detail=row["agent_state_detail"] if "agent_state_detail" in row.keys() else None,
            input_request_payload=input_request_payload,
        )
    
    def put_state(
        self, 
        context_id: str, 
        state: ContextState,
        expected_version: Optional[int] = None,
    ) -> int:
        """Put full state for a context with optimistic concurrency."""
        conn = self._get_connection(context_id)
        now = datetime.utcnow().isoformat()
        
        # Generate resume token
        resume_token = self._generate_resume_token_value(context_id, state.version + 1)
        
        # Serialize input_request_payload
        input_payload_json = None
        if state.input_request_payload:
            input_payload_json = json.dumps(redact_sensitive(state.input_request_payload))
        
        if expected_version is not None:
            # CAS update
            cursor = conn.execute("""
                UPDATE context_state 
                SET current_turn = ?, task_state = ?, summary = ?, 
                    version = version + 1, resume_token = ?,
                    agent_state_detail = ?, input_request_payload = ?,
                    updated_at = ?
                WHERE context_id = ? AND version = ?
            """, (
                state.current_turn,
                state.task_state,
                state.summary,
                resume_token,
                state.agent_state_detail,
                input_payload_json,
                now,
                context_id,
                expected_version,
            ))
            
            if cursor.rowcount == 0:
                row = conn.execute(
                    "SELECT version FROM context_state WHERE context_id = ?",
                    (context_id,)
                ).fetchone()
                actual = row["version"] if row else 0
                raise VersionConflictError(context_id, expected_version, actual)
        else:
            # Upsert
            conn.execute("""
                INSERT INTO context_state 
                (context_id, current_turn, task_state, summary, version, resume_token,
                 agent_state_detail, input_request_payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(context_id) DO UPDATE SET
                    current_turn = excluded.current_turn,
                    task_state = excluded.task_state,
                    summary = excluded.summary,
                    version = context_state.version + 1,
                    resume_token = excluded.resume_token,
                    agent_state_detail = excluded.agent_state_detail,
                    input_request_payload = excluded.input_request_payload,
                    updated_at = excluded.updated_at
            """, (
                context_id,
                state.current_turn,
                state.task_state,
                state.summary,
                resume_token,
                state.agent_state_detail,
                input_payload_json,
                state.created_at.isoformat(),
                now,
            ))
        
        # Clear and repopulate events
        conn.execute("DELETE FROM conversation_events WHERE context_id = ?", (context_id,))
        for event in state.events[-MAX_EVENTS_PER_CONTEXT:]:
            conn.execute("""
                INSERT INTO conversation_events 
                (context_id, event_type, payload, timestamp, turn_number, agent_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                context_id,
                event.event_type,
                json.dumps(redact_sensitive(event.payload)),
                event.timestamp.isoformat(),
                event.turn_number,
                event.agent_id,
                event.message_id,
            ))
        
        # Clear and repopulate facts
        conn.execute("DELETE FROM pocket_facts WHERE context_id = ?", (context_id,))
        for bucket, keys in state.facts.items():
            for key, value in list(keys.items())[-MAX_POCKET_FACTS_PER_BUCKET:]:
                conn.execute("""
                    INSERT INTO pocket_facts (context_id, bucket, key, value, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (context_id, bucket, key, json.dumps(redact_sensitive(value)), now))
        
        conn.commit()
        
        # Return new version
        row = conn.execute(
            "SELECT version FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        return row["version"]
    
    def append_event(
        self, 
        context_id: str, 
        event: ConversationEvent,
        expected_version: Optional[int] = None,
    ) -> int:
        """Append event with dedupe and optional CAS."""
        conn = self._get_connection(context_id)
        self._ensure_context(conn, context_id)
        
        # Check for duplicate message_id
        if event.message_id:
            existing = conn.execute("""
                SELECT 1 FROM conversation_events 
                WHERE context_id = ? AND message_id = ?
            """, (context_id, event.message_id)).fetchone()
            
            if existing:
                raise DuplicateMessageError(context_id, event.message_id)
        
        # CAS check if expected_version provided
        if expected_version is not None:
            row = conn.execute(
                "SELECT version FROM context_state WHERE context_id = ?",
                (context_id,)
            ).fetchone()
            actual = row["version"] if row else 1
            if actual != expected_version:
                raise VersionConflictError(context_id, expected_version, actual)
        
        # Insert event with redaction
        conn.execute("""
            INSERT INTO conversation_events 
            (context_id, event_type, payload, timestamp, turn_number, agent_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            context_id,
            event.event_type,
            json.dumps(redact_sensitive(event.payload)),
            event.timestamp.isoformat(),
            event.turn_number,
            event.agent_id,
            event.message_id,
        ))
        
        # Increment version
        new_version = self._increment_version(conn, context_id, None)
        
        # Trim to limit
        self._trim_events(conn, context_id)
        
        return new_version
    
    def get_events(self, context_id: str, limit: int = 50) -> List[ConversationEvent]:
        """Get recent events for context."""
        conn = self._get_connection(context_id)
        
        rows = conn.execute("""
            SELECT event_type, payload, timestamp, turn_number, agent_id, message_id
            FROM conversation_events
            WHERE context_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (context_id, limit)).fetchall()
        
        events = []
        for row in reversed(rows):  # Return in chronological order
            events.append(ConversationEvent(
                event_type=row["event_type"],
                payload=json.loads(row["payload"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                turn_number=row["turn_number"],
                agent_id=row["agent_id"],
                message_id=row["message_id"],
            ))
        return events
    
    def put_fact(
        self, 
        context_id: str, 
        fact: PocketFact,
        redact: bool = True,
    ) -> None:
        """Upsert a pocket fact with optional redaction."""
        conn = self._get_connection(context_id)
        self._ensure_context(conn, context_id)
        
        value = redact_sensitive(fact.value) if redact else fact.value
        
        # Calculate expires_at if TTL set
        expires_at = None
        if fact.ttl_seconds:
            from datetime import timedelta
            expires_at = (fact.timestamp + timedelta(seconds=fact.ttl_seconds)).isoformat()
        
        conn.execute("""
            INSERT OR REPLACE INTO pocket_facts 
            (context_id, bucket, key, value, timestamp, ttl_seconds, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            context_id,
            fact.bucket,
            fact.key,
            json.dumps(value),
            fact.timestamp.isoformat(),
            fact.ttl_seconds,
            expires_at,
        ))
        conn.commit()
        
        # Trim bucket to limit
        self._trim_facts(conn, context_id, fact.bucket)
    
    def get_fact(self, context_id: str, bucket: str, key: str) -> Optional[Any]:
        """Get a specific fact value."""
        conn = self._get_connection(context_id)
        
        row = conn.execute("""
            SELECT value FROM pocket_facts
            WHERE context_id = ? AND bucket = ? AND key = ?
        """, (context_id, bucket, key)).fetchone()
        
        if row:
            return json.loads(row["value"])
        return None
    
    def get_facts_by_bucket(self, context_id: str, bucket: str) -> Dict[str, Any]:
        """Get all facts in a bucket."""
        conn = self._get_connection(context_id)
        
        rows = conn.execute("""
            SELECT key, value FROM pocket_facts
            WHERE context_id = ? AND bucket = ?
        """, (context_id, bucket)).fetchall()
        
        return {row["key"]: json.loads(row["value"]) for row in rows}
    
    def update_summary(self, context_id: str, summary: ConversationSummary) -> None:
        """Update conversation summary (bounded size)."""
        conn = self._get_connection(context_id)
        self._ensure_context(conn, context_id)
        
        # Truncate to max size
        truncated = summary.summary_text[:MAX_SUMMARY_SIZE_CHARS]
        now = datetime.utcnow().isoformat()
        
        conn.execute("""
            UPDATE context_state 
            SET summary = ?, updated_at = ?
            WHERE context_id = ?
        """, (truncated, now, context_id))
        conn.commit()
    
    def get_summary(self, context_id: str) -> Optional[str]:
        """Get current summary text."""
        conn = self._get_connection(context_id)
        
        row = conn.execute(
            "SELECT summary FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        
        return row["summary"] if row else None
    
    def update_task_state(
        self, 
        context_id: str, 
        task_state: str, 
        turn: int,
        agent_state_detail: Optional[str] = None,
        input_request_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update task state with semantic detail."""
        conn = self._get_connection(context_id)
        self._ensure_context(conn, context_id)
        
        now = datetime.utcnow().isoformat()
        
        # Serialize and redact input_request_payload
        input_payload_json = None
        if input_request_payload:
            input_payload_json = json.dumps(redact_sensitive(input_request_payload))
        
        conn.execute("""
            UPDATE context_state 
            SET task_state = ?, current_turn = ?, 
                agent_state_detail = ?, input_request_payload = ?,
                updated_at = ?
            WHERE context_id = ?
        """, (task_state, turn, agent_state_detail, input_payload_json, now, context_id))
        conn.commit()
    
    def _generate_resume_token_value(self, context_id: str, version: int) -> str:
        """Generate a resume token for validation."""
        data = f"{context_id}:{version}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def generate_resume_token(self, context_id: str) -> str:
        """Generate a resume token for the current state."""
        conn = self._get_connection(context_id)
        
        row = conn.execute(
            "SELECT version FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        
        version = row["version"] if row else 1
        token = self._generate_resume_token_value(context_id, version)
        
        # Store the token
        now = datetime.utcnow().isoformat()
        conn.execute("""
            UPDATE context_state SET resume_token = ?, updated_at = ?
            WHERE context_id = ?
        """, (token, now, context_id))
        conn.commit()
        
        return token
    
    def validate_resume_token(self, context_id: str, token: str) -> bool:
        """Validate a resume token matches current state."""
        conn = self._get_connection(context_id)
        
        row = conn.execute(
            "SELECT resume_token FROM context_state WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        
        if not row or not row["resume_token"]:
            return False
        
        return row["resume_token"] == token
    
    def prune_expired(self, context_id: Optional[str] = None) -> int:
        """Prune expired facts and over-limit events."""
        now = datetime.utcnow().isoformat()
        total_pruned = 0
        
        if context_id:
            conn = self._get_connection(context_id)
            
            # Prune expired facts
            cursor = conn.execute("""
                DELETE FROM pocket_facts 
                WHERE context_id = ? AND expires_at IS NOT NULL AND expires_at < ?
            """, (context_id, now))
            total_pruned += cursor.rowcount
            
            # Prune over-limit events
            self._trim_events(conn, context_id)
            conn.commit()
        else:
            # Prune all contexts (requires shared db_path)
            if self._db_path:
                conn = self._get_connection()
                
                cursor = conn.execute("""
                    DELETE FROM pocket_facts 
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                """, (now,))
                total_pruned += cursor.rowcount
                conn.commit()
        
        return total_pruned

    # =========================================================================
    # DELEGATION OUTBOX IMPLEMENTATION
    # =========================================================================
    
    def save_outbox_message(
        self,
        context_id: str,
        message_id: str,
        target_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Save a delegation message to the outbox."""
        conn = self._get_connection(context_id)
        now = datetime.utcnow().isoformat()
        
        # Redact sensitive data before storage
        redacted_payload = redact_sensitive(payload)
        
        try:
            conn.execute("""
                INSERT INTO delegation_outbox 
                    (message_id, context_id, target_agent, message_type, 
                     payload, correlation_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                message_id,
                context_id,
                target_agent,
                message_type,
                json.dumps(redacted_payload),
                correlation_id,
                now,
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            raise DuplicateMessageError(context_id, message_id)
    
    def get_pending_outbox_messages(
        self,
        context_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get pending (undelivered) outbox messages."""
        # Need shared DB or specific context
        if context_id:
            conn = self._get_connection(context_id)
        elif self._db_path:
            conn = self._get_connection()
        else:
            return []  # No shared DB, can't query all contexts
        
        if context_id:
            cursor = conn.execute("""
                SELECT * FROM delegation_outbox
                WHERE context_id = ? AND status = 'pending'
                ORDER BY created_at
                LIMIT ?
            """, (context_id, limit))
        else:
            cursor = conn.execute("""
                SELECT * FROM delegation_outbox
                WHERE status = 'pending'
                ORDER BY created_at
                LIMIT ?
            """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "message_id": row["message_id"],
                "context_id": row["context_id"],
                "target_agent": row["target_agent"],
                "message_type": row["message_type"],
                "payload": json.loads(row["payload"]),
                "correlation_id": row["correlation_id"],
                "status": row["status"],
                "retry_count": row["retry_count"],
                "last_error": row["last_error"],
                "created_at": row["created_at"],
            })
        
        return results
    
    def mark_outbox_delivered(
        self,
        message_id: str,
        delivered_at: Optional[str] = None,
    ) -> bool:
        """Mark an outbox message as delivered."""
        # This needs to work across any context, so use shared DB if available
        if self._db_path:
            conn = self._get_connection()
        else:
            # Without shared DB, this won't work well
            return False
        
        now = delivered_at or datetime.utcnow().isoformat()
        
        cursor = conn.execute("""
            UPDATE delegation_outbox
            SET status = 'delivered', delivered_at = ?
            WHERE message_id = ? AND status = 'pending'
        """, (now, message_id))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def mark_outbox_failed(
        self,
        message_id: str,
        error: str,
        retry_count: int = 0,
    ) -> bool:
        """Mark an outbox message as failed."""
        if self._db_path:
            conn = self._get_connection()
        else:
            return False
        
        cursor = conn.execute("""
            UPDATE delegation_outbox
            SET status = 'failed', last_error = ?, retry_count = ?
            WHERE message_id = ?
        """, (error, retry_count, message_id))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def close(self) -> None:
        """Close all connections."""
        if hasattr(self._local, "connections"):
            for conn in self._local.connections.values():
                conn.close()
            self._local.connections.clear()


# =============================================================================
# POSTGRES IMPLEMENTATION STUB (production/multi-worker)
# =============================================================================

class PostgresStateStore(StateStore):
    """
    PostgreSQL-backed state store for production multi-worker deployments.
    
    REQUIREMENTS:
    - psycopg2-binary or psycopg2 package
    - PostgreSQL 12+ (for JSONB and ON CONFLICT)
    
    SETUP:
    1. Set STATE_STORE_BACKEND=postgres
    2. Set DATABASE_URL=postgresql://user:pass@host:5432/dbname
    3. Run schema migration (see SCHEMA below)
    
    SCHEMA (run once via migration):
    
        CREATE TABLE agent_context_state (
            context_id VARCHAR(255) PRIMARY KEY,
            current_turn INTEGER DEFAULT 1,
            task_state VARCHAR(50) DEFAULT 'pending',
            summary TEXT,
            version INTEGER DEFAULT 1,
            resume_token VARCHAR(64),
            agent_state_detail VARCHAR(50),
            input_request_payload JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE TABLE agent_conversation_events (
            id SERIAL PRIMARY KEY,
            context_id VARCHAR(255) NOT NULL REFERENCES agent_context_state(context_id) ON DELETE CASCADE,
            event_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            turn_number INTEGER NOT NULL,
            agent_id VARCHAR(255),
            message_id VARCHAR(255),
            UNIQUE(context_id, message_id)
        );
        CREATE INDEX idx_agent_events_context ON agent_conversation_events(context_id, timestamp DESC);
        CREATE INDEX idx_agent_events_message ON agent_conversation_events(context_id, message_id) WHERE message_id IS NOT NULL;
        
        CREATE TABLE agent_pocket_facts (
            context_id VARCHAR(255) NOT NULL REFERENCES agent_context_state(context_id) ON DELETE CASCADE,
            bucket VARCHAR(100) NOT NULL,
            key VARCHAR(255) NOT NULL,
            value JSONB NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            ttl_seconds INTEGER,
            expires_at TIMESTAMPTZ,
            PRIMARY KEY (context_id, bucket, key)
        );
        CREATE INDEX idx_agent_facts_bucket ON agent_pocket_facts(context_id, bucket);
        CREATE INDEX idx_agent_facts_expires ON agent_pocket_facts(expires_at) WHERE expires_at IS NOT NULL;
        
        -- Delegation outbox (agent-to-agent messaging)
        CREATE TABLE agent_delegation_outbox (
            message_id VARCHAR(255) PRIMARY KEY,
            context_id VARCHAR(255) NOT NULL REFERENCES agent_context_state(context_id) ON DELETE CASCADE,
            target_agent VARCHAR(255) NOT NULL,
            message_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            correlation_id VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            delivered_at TIMESTAMPTZ
        );
        CREATE INDEX idx_agent_outbox_status ON agent_delegation_outbox(status, created_at);
        CREATE INDEX idx_agent_outbox_context ON agent_delegation_outbox(context_id, status);
    
    CONCURRENCY:
    - Uses PostgreSQL's row-level locking via SELECT ... FOR UPDATE
    - CAS updates via version column with conditional UPDATE
    - Dedupe via UNIQUE constraint on (context_id, message_id)
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize Postgres state store.
        
        Args:
            connection_string: PostgreSQL connection string
                               (default: DATABASE_URL env var)
        
        Raises:
            ValueError: If no connection string provided
            ImportError: If psycopg2 not installed
        """
        self._connection_string = connection_string or os.environ.get("DATABASE_URL")
        if not self._connection_string:
            raise ValueError(
                "PostgresStateStore requires DATABASE_URL env var or connection_string. "
                "Example: postgresql://user:pass@localhost:5432/agent_skills"
            )
        
        # Import psycopg2 - raises ImportError if not installed
        try:
            import psycopg2
            import psycopg2.extras
            self._psycopg2 = psycopg2
            self._extras = psycopg2.extras
        except ImportError:
            raise ImportError(
                "PostgresStateStore requires psycopg2. Install with: "
                "pip install psycopg2-binary"
            )
        
        # Thread-local connections for safety
        self._local = threading.local()
    
    def _get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None or self._local.conn.closed:
            self._local.conn = self._psycopg2.connect(
                self._connection_string,
                cursor_factory=self._extras.RealDictCursor
            )
            self._local.conn.autocommit = False
        return self._local.conn
    
    def _ensure_context(self, cursor, context_id: str) -> int:
        """Ensure context_state row exists, return current version."""
        cursor.execute("""
            INSERT INTO agent_context_state (context_id, version, created_at, updated_at)
            VALUES (%s, 1, NOW(), NOW())
            ON CONFLICT (context_id) DO NOTHING
        """, (context_id,))
        
        cursor.execute(
            "SELECT version FROM agent_context_state WHERE context_id = %s",
            (context_id,)
        )
        row = cursor.fetchone()
        return row["version"] if row else 1
    
    def _generate_resume_token_value(self, context_id: str, version: int) -> str:
        """Generate a resume token for validation."""
        data = f"{context_id}:{version}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get_state(self, context_id: str) -> Optional[ContextState]:
        """Get full state for a context, including version."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM agent_context_state WHERE context_id = %s",
                    (context_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                # Get events
                events = self.get_events(context_id, limit=MAX_EVENTS_PER_CONTEXT)
                
                # Get facts
                cur.execute(
                    "SELECT bucket, key, value FROM agent_pocket_facts WHERE context_id = %s",
                    (context_id,)
                )
                facts: Dict[str, Dict[str, Any]] = {}
                for fact_row in cur.fetchall():
                    bucket = fact_row["bucket"]
                    if bucket not in facts:
                        facts[bucket] = {}
                    facts[bucket][fact_row["key"]] = fact_row["value"]
                
                return ContextState(
                    context_id=context_id,
                    current_turn=row["current_turn"],
                    task_state=row["task_state"],
                    events=events,
                    facts=facts,
                    summary=row["summary"],
                    created_at=row["created_at"] or datetime.utcnow(),
                    updated_at=row["updated_at"] or datetime.utcnow(),
                    version=row["version"],
                    resume_token=row["resume_token"],
                    agent_state_detail=row["agent_state_detail"],
                    input_request_payload=row["input_request_payload"],
                )
        except Exception:
            conn.rollback()
            raise
    
    def put_state(
        self, 
        context_id: str, 
        state: ContextState,
        expected_version: Optional[int] = None,
    ) -> int:
        """Put full state for a context with optimistic concurrency."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                resume_token = self._generate_resume_token_value(context_id, state.version + 1)
                input_payload = redact_sensitive(state.input_request_payload) if state.input_request_payload else None
                
                if expected_version is not None:
                    # CAS update
                    cur.execute("""
                        UPDATE agent_context_state 
                        SET current_turn = %s, task_state = %s, summary = %s,
                            version = version + 1, resume_token = %s,
                            agent_state_detail = %s, input_request_payload = %s,
                            updated_at = NOW()
                        WHERE context_id = %s AND version = %s
                        RETURNING version
                    """, (
                        state.current_turn,
                        state.task_state,
                        state.summary,
                        resume_token,
                        state.agent_state_detail,
                        json.dumps(input_payload) if input_payload else None,
                        context_id,
                        expected_version,
                    ))
                    
                    result = cur.fetchone()
                    if not result:
                        cur.execute(
                            "SELECT version FROM agent_context_state WHERE context_id = %s",
                            (context_id,)
                        )
                        row = cur.fetchone()
                        actual = row["version"] if row else 0
                        conn.rollback()
                        raise VersionConflictError(context_id, expected_version, actual)
                    new_version = result["version"]
                else:
                    # Upsert
                    cur.execute("""
                        INSERT INTO agent_context_state 
                        (context_id, current_turn, task_state, summary, version, resume_token,
                         agent_state_detail, input_request_payload, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, NOW())
                        ON CONFLICT (context_id) DO UPDATE SET
                            current_turn = EXCLUDED.current_turn,
                            task_state = EXCLUDED.task_state,
                            summary = EXCLUDED.summary,
                            version = agent_context_state.version + 1,
                            resume_token = EXCLUDED.resume_token,
                            agent_state_detail = EXCLUDED.agent_state_detail,
                            input_request_payload = EXCLUDED.input_request_payload,
                            updated_at = NOW()
                        RETURNING version
                    """, (
                        context_id,
                        state.current_turn,
                        state.task_state,
                        state.summary,
                        resume_token,
                        state.agent_state_detail,
                        json.dumps(input_payload) if input_payload else None,
                        state.created_at,
                    ))
                    new_version = cur.fetchone()["version"]
                
                # Clear and repopulate events (bounded)
                cur.execute("DELETE FROM agent_conversation_events WHERE context_id = %s", (context_id,))
                for event in state.events[-MAX_EVENTS_PER_CONTEXT:]:
                    cur.execute("""
                        INSERT INTO agent_conversation_events 
                        (context_id, event_type, payload, timestamp, turn_number, agent_id, message_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        context_id,
                        event.event_type,
                        json.dumps(redact_sensitive(event.payload)),
                        event.timestamp,
                        event.turn_number,
                        event.agent_id,
                        event.message_id,
                    ))
                
                # Clear and repopulate facts (bounded per bucket)
                cur.execute("DELETE FROM agent_pocket_facts WHERE context_id = %s", (context_id,))
                for bucket, keys in state.facts.items():
                    for key, value in list(keys.items())[-MAX_POCKET_FACTS_PER_BUCKET:]:
                        cur.execute("""
                            INSERT INTO agent_pocket_facts 
                            (context_id, bucket, key, value, timestamp)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (context_id, bucket, key, json.dumps(redact_sensitive(value))))
                
                conn.commit()
                return new_version
        except Exception:
            conn.rollback()
            raise
    
    def append_event(
        self, 
        context_id: str, 
        event: ConversationEvent,
        expected_version: Optional[int] = None,
    ) -> int:
        """Append event with dedupe and optional CAS."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                self._ensure_context(cur, context_id)
                
                # CAS check if expected_version provided
                if expected_version is not None:
                    cur.execute(
                        "SELECT version FROM agent_context_state WHERE context_id = %s FOR UPDATE",
                        (context_id,)
                    )
                    row = cur.fetchone()
                    actual = row["version"] if row else 1
                    if actual != expected_version:
                        conn.rollback()
                        raise VersionConflictError(context_id, expected_version, actual)
                
                # Insert event (unique constraint handles dedupe)
                try:
                    cur.execute("""
                        INSERT INTO agent_conversation_events 
                        (context_id, event_type, payload, timestamp, turn_number, agent_id, message_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        context_id,
                        event.event_type,
                        json.dumps(redact_sensitive(event.payload)),
                        event.timestamp,
                        event.turn_number,
                        event.agent_id,
                        event.message_id,
                    ))
                except self._psycopg2.IntegrityError as e:
                    conn.rollback()
                    if "unique" in str(e).lower() and event.message_id:
                        raise DuplicateMessageError(context_id, event.message_id)
                    raise
                
                # Increment version
                cur.execute("""
                    UPDATE agent_context_state 
                    SET version = version + 1, updated_at = NOW()
                    WHERE context_id = %s
                    RETURNING version
                """, (context_id,))
                new_version = cur.fetchone()["version"]
                
                # Trim to limit (delete oldest beyond MAX)
                cur.execute("""
                    DELETE FROM agent_conversation_events
                    WHERE context_id = %s AND id NOT IN (
                        SELECT id FROM agent_conversation_events
                        WHERE context_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    )
                """, (context_id, context_id, MAX_EVENTS_PER_CONTEXT))
                
                conn.commit()
                return new_version
        except Exception:
            conn.rollback()
            raise
    
    def get_events(self, context_id: str, limit: int = 50) -> List[ConversationEvent]:
        """Get recent events for context."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT event_type, payload, timestamp, turn_number, agent_id, message_id
                    FROM agent_conversation_events
                    WHERE context_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (context_id, limit))
                
                events = []
                for row in reversed(cur.fetchall()):  # Chronological order
                    events.append(ConversationEvent(
                        event_type=row["event_type"],
                        payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]),
                        timestamp=row["timestamp"],
                        turn_number=row["turn_number"],
                        agent_id=row["agent_id"],
                        message_id=row["message_id"],
                    ))
                return events
        except Exception:
            conn.rollback()
            raise
    
    def put_fact(
        self, 
        context_id: str, 
        fact: PocketFact,
        redact: bool = True,
    ) -> None:
        """Upsert a pocket fact with optional redaction."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                self._ensure_context(cur, context_id)
                
                value = redact_sensitive(fact.value) if redact else fact.value
                
                # Calculate expires_at if TTL set
                expires_at = None
                if fact.ttl_seconds:
                    from datetime import timedelta
                    expires_at = fact.timestamp + timedelta(seconds=fact.ttl_seconds)
                
                cur.execute("""
                    INSERT INTO agent_pocket_facts 
                    (context_id, bucket, key, value, timestamp, ttl_seconds, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (context_id, bucket, key) DO UPDATE SET
                        value = EXCLUDED.value,
                        timestamp = EXCLUDED.timestamp,
                        ttl_seconds = EXCLUDED.ttl_seconds,
                        expires_at = EXCLUDED.expires_at
                """, (
                    context_id,
                    fact.bucket,
                    fact.key,
                    json.dumps(value),
                    fact.timestamp,
                    fact.ttl_seconds,
                    expires_at,
                ))
                
                # Trim bucket to limit
                cur.execute("""
                    DELETE FROM agent_pocket_facts
                    WHERE context_id = %s AND bucket = %s AND key NOT IN (
                        SELECT key FROM agent_pocket_facts
                        WHERE context_id = %s AND bucket = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    )
                """, (context_id, fact.bucket, context_id, fact.bucket, MAX_POCKET_FACTS_PER_BUCKET))
                
                conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def get_fact(self, context_id: str, bucket: str, key: str) -> Optional[Any]:
        """Get a specific fact value."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT value FROM agent_pocket_facts
                    WHERE context_id = %s AND bucket = %s AND key = %s
                """, (context_id, bucket, key))
                row = cur.fetchone()
                if row:
                    val = row["value"]
                    return val if isinstance(val, (dict, list)) else json.loads(val)
                return None
        except Exception:
            conn.rollback()
            raise
    
    def get_facts_by_bucket(self, context_id: str, bucket: str) -> Dict[str, Any]:
        """Get all facts in a bucket."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT key, value FROM agent_pocket_facts
                    WHERE context_id = %s AND bucket = %s
                """, (context_id, bucket))
                result = {}
                for row in cur.fetchall():
                    val = row["value"]
                    result[row["key"]] = val if isinstance(val, (dict, list)) else json.loads(val)
                return result
        except Exception:
            conn.rollback()
            raise
    
    def update_summary(self, context_id: str, summary: ConversationSummary) -> None:
        """Update conversation summary (bounded size)."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                self._ensure_context(cur, context_id)
                truncated = summary.summary_text[:MAX_SUMMARY_SIZE_CHARS]
                cur.execute("""
                    UPDATE agent_context_state 
                    SET summary = %s, updated_at = NOW()
                    WHERE context_id = %s
                """, (truncated, context_id))
                conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def get_summary(self, context_id: str) -> Optional[str]:
        """Get current summary text."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT summary FROM agent_context_state WHERE context_id = %s",
                    (context_id,)
                )
                row = cur.fetchone()
                return row["summary"] if row else None
        except Exception:
            conn.rollback()
            raise
    
    def update_task_state(
        self, 
        context_id: str, 
        task_state: str, 
        turn: int,
        agent_state_detail: Optional[str] = None,
        input_request_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update task state with semantic detail."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                self._ensure_context(cur, context_id)
                
                input_payload = None
                if input_request_payload:
                    input_payload = json.dumps(redact_sensitive(input_request_payload))
                
                cur.execute("""
                    UPDATE agent_context_state 
                    SET task_state = %s, current_turn = %s,
                        agent_state_detail = %s, input_request_payload = %s,
                        updated_at = NOW()
                    WHERE context_id = %s
                """, (task_state, turn, agent_state_detail, input_payload, context_id))
                conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def generate_resume_token(self, context_id: str) -> str:
        """Generate a resume token for the current state."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT version FROM agent_context_state WHERE context_id = %s FOR UPDATE",
                    (context_id,)
                )
                row = cur.fetchone()
                version = row["version"] if row else 1
                
                token = self._generate_resume_token_value(context_id, version)
                
                cur.execute("""
                    UPDATE agent_context_state 
                    SET resume_token = %s, updated_at = NOW()
                    WHERE context_id = %s
                """, (token, context_id))
                conn.commit()
                return token
        except Exception:
            conn.rollback()
            raise
    
    def validate_resume_token(self, context_id: str, token: str) -> bool:
        """Validate a resume token matches current state."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT resume_token FROM agent_context_state WHERE context_id = %s",
                    (context_id,)
                )
                row = cur.fetchone()
                if not row or not row["resume_token"]:
                    return False
                return row["resume_token"] == token
        except Exception:
            conn.rollback()
            raise
    
    def prune_expired(self, context_id: Optional[str] = None) -> int:
        """Prune expired facts and over-limit events."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                total_pruned = 0
                
                if context_id:
                    # Prune expired facts for specific context
                    cur.execute("""
                        DELETE FROM agent_pocket_facts 
                        WHERE context_id = %s AND expires_at IS NOT NULL AND expires_at < NOW()
                    """, (context_id,))
                    total_pruned += cur.rowcount
                    
                    # Prune over-limit events
                    cur.execute("""
                        DELETE FROM agent_conversation_events
                        WHERE context_id = %s AND id NOT IN (
                            SELECT id FROM agent_conversation_events
                            WHERE context_id = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        )
                    """, (context_id, context_id, MAX_EVENTS_PER_CONTEXT))
                    total_pruned += cur.rowcount
                else:
                    # Prune all expired facts
                    cur.execute("""
                        DELETE FROM agent_pocket_facts 
                        WHERE expires_at IS NOT NULL AND expires_at < NOW()
                    """)
                    total_pruned += cur.rowcount
                
                conn.commit()
                return total_pruned
        except Exception:
            conn.rollback()
            raise
    
    # =========================================================================
    # DELEGATION OUTBOX IMPLEMENTATION
    # =========================================================================
    
    def save_outbox_message(
        self,
        context_id: str,
        message_id: str,
        target_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Save a delegation message to the outbox."""
        conn = self._get_connection()
        
        # Redact sensitive data before storage
        redacted_payload = redact_sensitive(payload)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_delegation_outbox 
                        (message_id, context_id, target_agent, message_type, 
                         payload, correlation_id, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
                """, (
                    message_id,
                    context_id,
                    target_agent,
                    message_type,
                    json.dumps(redacted_payload),
                    correlation_id,
                ))
                conn.commit()
        except Exception as e:
            conn.rollback()
            # Check for unique constraint violation
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                raise DuplicateMessageError(f"Outbox message {message_id} already exists")
            raise
    
    def get_pending_outbox_messages(
        self,
        context_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get pending (undelivered) outbox messages."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                if context_id:
                    cur.execute("""
                        SELECT * FROM agent_delegation_outbox
                        WHERE context_id = %s AND status = 'pending'
                        ORDER BY created_at
                        LIMIT %s
                    """, (context_id, limit))
                else:
                    cur.execute("""
                        SELECT * FROM agent_delegation_outbox
                        WHERE status = 'pending'
                        ORDER BY created_at
                        LIMIT %s
                    """, (limit,))
                
                results = []
                for row in cur.fetchall():
                    results.append({
                        "message_id": row["message_id"],
                        "context_id": row["context_id"],
                        "target_agent": row["target_agent"],
                        "message_type": row["message_type"],
                        "payload": row["payload"],  # Already JSONB
                        "correlation_id": row["correlation_id"],
                        "status": row["status"],
                        "retry_count": row["retry_count"],
                        "last_error": row["last_error"],
                        "created_at": str(row["created_at"]) if row["created_at"] else None,
                    })
                
                return results
        except Exception:
            conn.rollback()
            raise
    
    def mark_outbox_delivered(
        self,
        message_id: str,
        delivered_at: Optional[str] = None,
    ) -> bool:
        """Mark an outbox message as delivered."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                if delivered_at:
                    cur.execute("""
                        UPDATE agent_delegation_outbox
                        SET status = 'delivered', delivered_at = %s
                        WHERE message_id = %s AND status = 'pending'
                    """, (delivered_at, message_id))
                else:
                    cur.execute("""
                        UPDATE agent_delegation_outbox
                        SET status = 'delivered', delivered_at = NOW()
                        WHERE message_id = %s AND status = 'pending'
                    """, (message_id,))
                
                conn.commit()
                return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
    
    def mark_outbox_failed(
        self,
        message_id: str,
        error: str,
        retry_count: int = 0,
    ) -> bool:
        """Mark an outbox message as failed."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_delegation_outbox
                    SET status = 'failed', last_error = %s, retry_count = %s
                    WHERE message_id = %s
                """, (error, retry_count, message_id))
                
                conn.commit()
                return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
    
    def close(self) -> None:
        """Close connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

# Environment variable for backend selection
STATE_STORE_BACKEND_ENV = "STATE_STORE_BACKEND"
STATE_STORE_BACKENDS = {"sqlite", "postgres"}


def create_state_store(
    db_path: Path | str | None = None,
    shared: bool = False,
    backend: Optional[str] = None,
) -> StateStore:
    """
    Create a state store instance based on configuration.
    
    Backend selection (in order of precedence):
    1. Explicit `backend` parameter
    2. STATE_STORE_BACKEND environment variable
    3. Default: "sqlite"
    
    Args:
        db_path: Explicit path to database file (SQLite only)
        shared: If True, use shared .state/agent_state.db (SQLite only)
        backend: Override backend selection ("sqlite" or "postgres")
    
    Returns:
        StateStore instance
    
    Environment Variables:
        STATE_STORE_BACKEND: "sqlite" (default, dev) or "postgres" (production)
        DATABASE_URL: PostgreSQL connection string (required if backend=postgres)
    
    Examples:
        # Dev (SQLite, per-context)
        store = create_state_store()
        
        # Dev (SQLite, shared)
        store = create_state_store(shared=True)
        
        # Production (PostgreSQL)
        os.environ["STATE_STORE_BACKEND"] = "postgres"
        os.environ["DATABASE_URL"] = "postgresql://..."
        store = create_state_store()
    """
    selected_backend = backend or os.environ.get(STATE_STORE_BACKEND_ENV, "sqlite")
    
    if selected_backend not in STATE_STORE_BACKENDS:
        raise ValueError(
            f"Unknown STATE_STORE_BACKEND: {selected_backend}. "
            f"Valid options: {STATE_STORE_BACKENDS}"
        )
    
    if selected_backend == "postgres":
        return PostgresStateStore()
    else:
        return SQLiteStateStore(db_path=db_path, shared=shared)
