import sqlite3
import hashlib
import secrets
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "collection.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                set_name TEXT,
                set_code TEXT,
                card_number TEXT,
                rarity TEXT,
                condition TEXT DEFAULT 'NM',
                image_url TEXT,
                date_added TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False


def register_user(username: str, password: str) -> tuple[bool, str]:
    if len(username.strip()) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username.strip().lower(), _hash_password(password)),
            )
            conn.commit()
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "Username already taken."


def login_user(username: str, password: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    if row and _verify_password(password, row["password_hash"]):
        return {"id": row["id"], "username": row["username"]}
    return None


def get_collection(user_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM collection WHERE user_id = ? ORDER BY date_added DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_to_collection(user_id: int, card: dict, condition: str = "NM") -> int:
    image_url = card.get("images", {}).get("small", "")
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO collection
               (user_id, card_id, card_name, set_name, set_code, card_number, rarity, condition, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                card.get("id", ""),
                card.get("name", ""),
                card.get("set_name", ""),
                card.get("set_code", ""),
                card.get("number", ""),
                card.get("rarity", ""),
                condition,
                image_url,
            ),
        )
        conn.commit()
        return cur.lastrowid


def remove_from_collection(user_id: int, entry_id: int):
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM collection WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
        conn.commit()
