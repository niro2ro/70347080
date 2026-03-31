import sqlite3
from contextlib import contextmanager
from typing import Optional, List

DB_PATH = "hiro.db"


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            INSERT OR IGNORE INTO users (user_id, name) VALUES
            (0, 'ひろき'), (1, '父'), (2, '母'), (3, 'おねーちゃん'), (4, 'おにーちゃん');

            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                content TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                ai_response TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_users() -> List:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY user_id").fetchall()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def get_watchlist(user_id: int) -> List:
    with get_conn() as conn:
        return conn.execute(
            "SELECT ticker FROM watchlists WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()


def add_to_watchlist(user_id: int, ticker: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlists (user_id, ticker) VALUES (?, ?)",
            (user_id, ticker)
        )


def remove_from_watchlist(user_id: int, ticker: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM watchlists WHERE user_id = ? AND ticker = ?",
            (user_id, ticker)
        )


def is_in_watchlist(user_id: int, ticker: str) -> bool:
    with get_conn() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM watchlists WHERE user_id = ? AND ticker = ?",
            (user_id, ticker)
        ).fetchone()
        return result[0] > 0


def get_memo(user_id: int, ticker: str) -> str:
    with get_conn() as conn:
        result = conn.execute(
            "SELECT content FROM memos WHERE user_id = ? AND ticker = ?",
            (user_id, ticker)
        ).fetchone()
        return result["content"] if result else ""


def save_memo(user_id: int, ticker: str, content: str):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM memos WHERE user_id = ? AND ticker = ?",
            (user_id, ticker)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memos SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (content, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO memos (user_id, ticker, content) VALUES (?, ?, ?)",
                (user_id, ticker, content)
            )


def save_analysis_history(user_id: int, ticker: str, ai_response: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO analysis_history (user_id, ticker, ai_response) VALUES (?, ?, ?)",
            (user_id, ticker, ai_response)
        )


def get_analysis_history(user_id: int, ticker: str = None, limit: int = 50) -> List:
    with get_conn() as conn:
        if ticker:
            return conn.execute(
                """SELECT ticker, ai_response, created_at
                   FROM analysis_history WHERE user_id = ? AND ticker = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, ticker, limit),
            ).fetchall()
        return conn.execute(
            """SELECT ticker, ai_response, created_at
               FROM analysis_history WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
