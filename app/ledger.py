"""SQLite access. Balances are always computed by SQL SUM, never by the model or Python."""
import difflib
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from .schemas import Kind

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    amount      INTEGER NOT NULL CHECK (amount > 0),
    kind        TEXT NOT NULL CHECK (kind IN ('udhaar', 'payment')),
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_entries_customer ON entries(customer_id);
"""

SIMILARITY_CUTOFF = 0.75


def _norm(name: str) -> str:
    return " ".join(name.split()).casefold()


class Ledger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(parent, exist_ok=True)
        # An in-memory DB lives only as long as its connection, so keep one open.
        self._memory_conn = self._open() if db_path == ":memory:" else None
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _conn(self):
        conn = self._memory_conn or self._open()
        try:
            with conn:  # commit or roll back
                yield conn
        finally:
            if conn is not self._memory_conn:
                conn.close()

    # ---- names -------------------------------------------------------------

    def customer_names(self) -> list[str]:
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT name FROM customers ORDER BY name")]

    # ---- writes ------------------------------------------------------------

    def add_entry(self, customer_name: str, amount: int, kind: Kind,
                  note: Optional[str] = None) -> int:
        """Insert an entry, creating the customer if needed. Returns the entry id.

        Callers must only reach this after explicit user confirmation.
        """
        name = " ".join(customer_name.split())
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO customers (name) VALUES (?)", (name,))
            cid = c.execute("SELECT id FROM customers WHERE name = ?", (name,)).fetchone()[0]
            cur = c.execute(
                "INSERT INTO entries (customer_id, amount, kind, note) VALUES (?, ?, ?, ?)",
                (cid, amount, kind, note),
            )
            return cur.lastrowid

    # ---- reads -------------------------------------------------------------

    def balance(self, customer_name: str) -> int:
        """udhaar adds, payment subtracts. Positive = customer owes the shopkeeper."""
        with self._conn() as c:
            row = c.execute(
                """
                SELECT COALESCE(SUM(CASE e.kind WHEN 'udhaar' THEN e.amount
                                                ELSE -e.amount END), 0)
                FROM customers cu LEFT JOIN entries e ON e.customer_id = cu.id
                WHERE cu.name = ?
                """,
                (customer_name,),
            ).fetchone()
        return int(row[0])

    def all_balances(self) -> list[tuple[str, int]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT cu.name,
                       COALESCE(SUM(CASE e.kind WHEN 'udhaar' THEN e.amount
                                                ELSE -e.amount END), 0)
                FROM customers cu LEFT JOIN entries e ON e.customer_id = cu.id
                GROUP BY cu.id ORDER BY cu.name
                """
            ).fetchall()
        return [(n, int(b)) for n, b in rows]


def resolve_name(name: str, existing: list[str]) -> tuple[str, bool, list[str]]:
    """Map a spoken name onto the existing customers.

    Returns (name_to_use, is_new, similar_names).
    - Exact match ignoring case/whitespace: reuse the stored spelling.
    - Otherwise it is a new customer; near matches are returned as hints only.
      They are never merged automatically, because attaching a debt to the
      wrong person is worse than asking the user to look.
    """
    clean = " ".join(name.split())
    by_norm = {_norm(n): n for n in existing}
    hit = by_norm.get(_norm(clean))
    if hit is not None:
        return hit, False, []
    similar = difflib.get_close_matches(
        _norm(clean), list(by_norm), n=3, cutoff=SIMILARITY_CUTOFF
    )
    return clean, True, [by_norm[s] for s in similar]
