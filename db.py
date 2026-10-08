import sqlite3, time

SESSION_RETENTION_SECONDS = 3 * 60

conn = sqlite3.connect("chocobot.db", check_same_thread=False)
# Remove profiles saved by earlier versions; profile data is no longer collected or retained.
conn.execute("DROP TABLE IF EXISTS customers")
conn.execute("""CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at REAL)""")
conn.commit()


def save_message(session_id, role, content):
    now = time.time()
    purge_expired_sessions(now)
    conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                 (session_id, role, content, now))
    conn.commit()


def purge_expired_sessions(now=None):
    cutoff = (time.time() if now is None else now) - SESSION_RETENTION_SECONDS
    conn.execute(
        """DELETE FROM messages WHERE session_id IN (
               SELECT session_id FROM messages GROUP BY session_id HAVING MAX(created_at) <= ?
           )""",
        (cutoff,),
    )
    conn.commit()


def get_history(session_id):
    rows = conn.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    return [{"role": r, "content": c} for r, c in rows]


def delete_session(session_id):
    conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
    conn.commit()


def get_all():
    msgs = conn.execute("SELECT id, session_id, role, content, created_at FROM messages ORDER BY id DESC LIMIT 200").fetchall()
    return {
        "messages": [dict(zip(["id", "session_id", "role", "content", "created_at"], r)) for r in msgs],
    }
