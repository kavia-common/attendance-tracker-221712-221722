import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2 import pool


class SingletonConnectionPool:
    """Thread-safe singleton wrapper around psycopg2 connection pool."""

    _instance_lock = threading.Lock()
    _instance: Optional["SingletonConnectionPool"] = None

    def __init__(self) -> None:
        # Initialize connection pool from environment variables.
        # PUBLIC_INTERFACE
        # Use environment variables; they must be provided via .env by the orchestrator.
        db_url = os.getenv("POSTGRES_URL")
        db_user = os.getenv("POSTGRES_USER")
        db_password = os.getenv("POSTGRES_PASSWORD")
        db_name = os.getenv("POSTGRES_DB")
        db_port = os.getenv("POSTGRES_PORT")

        if not any([db_url, db_user, db_password, db_name, db_port]):
            # Allow either full URL or individual params. Raise explicit error if neither is present.
            raise RuntimeError(
                "Database configuration is missing. Ensure POSTGRES_URL or "
                "POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB/POSTGRES_PORT are set in .env."
            )

        if db_url:
            dsn = db_url
        else:
            host = "localhost"
            dsn = f"dbname={db_name} user={db_user} password={db_password} host={host} port={db_port}"

        minconn = int(os.getenv("DB_POOL_MINCONN", "1"))
        maxconn = int(os.getenv("DB_POOL_MAXCONN", "5"))

        self._pool = pool.SimpleConnectionPool(minconn=minconn, maxconn=maxconn, dsn=dsn)

    @classmethod
    def instance(cls) -> "SingletonConnectionPool":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def getconn(self):
        return self._pool.getconn()

    def putconn(self, conn):
        return self._pool.putconn(conn)

    def closeall(self):
        return self._pool.closeall()


@contextmanager
def get_db_connection():
    """Context manager to get and return a pooled DB connection."""
    pool_instance = SingletonConnectionPool.instance()
    conn = pool_instance.getconn()
    try:
        yield conn
    finally:
        pool_instance.putconn(conn)


def _execute(cur, query: str, params: Optional[Iterable[Any]] = None):
    cur.execute(query, params if params is not None else None)


# PUBLIC_INTERFACE
def execute_query(
    query: str, params: Optional[Iterable[Any]] = None, fetch: str = "all"
) -> Tuple[List[Tuple], Optional[List[str]]]:
    """
    Execute a SQL query using a pooled connection.

    Args:
        query: SQL string with placeholders.
        params: Optional iterable of parameters.
        fetch: one of "all", "one", or "none". If "none", no rows will be fetched.

    Returns:
        A tuple (rows, columns) where rows is a list of tuples and columns is a list of column names (or None).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _execute(cur, query, params)
            rows: List[Tuple] = []
            cols: Optional[List[str]] = None
            try:
                if fetch == "all":
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description] if cur.description else None
                elif fetch == "one":
                    row = cur.fetchone()
                    rows = [row] if row else []
                    cols = [desc[0] for desc in cur.description] if cur.description else None
                else:
                    rows = []
                    cols = None
            except psycopg2.ProgrammingError:
                # No results to fetch
                rows = []
                cols = None
        conn.commit()
    return rows, cols


# PUBLIC_INTERFACE
def execute_many(query: str, seq_of_params: Iterable[Iterable[Any]]) -> int:
    """
    Execute many insert/update statements efficiently.

    Args:
        query: SQL with placeholders.
        seq_of_params: list/iterable of params.

    Returns:
        Number of rows affected (best-effort).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, seq_of_params)
        conn.commit()
        return cur.rowcount if hasattr(cur, "rowcount") else 0


# PUBLIC_INTERFACE
def ensure_schema() -> None:
    """
    Ensure required tables exist. Idempotent.
    Tables:
      - users (id serial pk, email unique, role enum-like text, name)
      - classes (id serial pk, name, teacher_id fk users)
      - attendance (id serial pk, class_id, user_id, status, ts)
      - class_members (class_id, user_id) membership
    """
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS classes (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS class_members (
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (class_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
            ts TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        # Simple indexes
        "CREATE INDEX IF NOT EXISTS idx_attendance_class_ts ON attendance(class_id, ts DESC)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_user_ts ON attendance(user_id, ts DESC)",
    ]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for ddl in ddl_statements:
                cur.execute(ddl)
        conn.commit()


# Simple in-memory pubsub for SSE broadcast across workers (best-effort within single process)
class SseBroker:
    """Lightweight SSE broker for broadcasting to connected clients (same process)."""

    def __init__(self) -> None:
        self._clients: List[Tuple[int, "SseClient"]] = []
        self._lock = threading.Lock()
        self._next_id = 1

    def register(self, client: "SseClient") -> int:
        with self._lock:
            cid = self._next_id
            self._next_id += 1
            self._clients.append((cid, client))
            return cid

    def unregister(self, client_id: int) -> None:
        with self._lock:
            self._clients = [(cid, c) for cid, c in self._clients if cid != client_id]

    def publish(self, event: str, data: Dict[str, Any]) -> None:
        with self._lock:
            for _, client in list(self._clients):
                client.send(event, data)


class SseClient:
    """A single SSE client queue."""

    def __init__(self) -> None:
        self._queue: List[str] = []
        self._cond = threading.Condition()

    def send(self, event: str, data: Dict[str, Any]) -> None:
        payload = f"event: {event}\ndata: {data}\n\n"
        with self._cond:
            self._queue.append(payload)
            self._cond.notify()

    def stream(self):
        # Generator for Flask Response streaming
        # Send a comment every 15s to keep connection alive
        keepalive_interval = 15
        last_ping = time.time()
        while True:
            with self._cond:
                if not self._queue:
                    # Wait or ping
                    remaining = max(0, keepalive_interval - (time.time() - last_ping))
                    self._cond.wait(timeout=remaining if remaining > 0 else 0.1)
                items = list(self._queue)
                self._queue.clear()
            now = time.time()
            if now - last_ping >= keepalive_interval:
                yield ": keep-alive\n\n"
                last_ping = now
            for payload in items:
                yield payload


# Single process global broker
sse_broker = SseBroker()
