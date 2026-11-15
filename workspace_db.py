# workspace_db.py
import os
import sqlite3

# Always next to this file, regardless of the working directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspaces_state.sqlite")

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            last_commit TEXT
        )
    """)
    return conn

def init_db():
    with _connect():
        pass

def get_workspace(workspace_id: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT repo_url, last_commit FROM workspaces WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        return {"repo_url": row[0], "last_commit": row[1]} if row else None

def update_workspace(workspace_id: str, repo_url: str, last_commit: str):
    with _connect() as conn:
        conn.execute("""
            INSERT INTO workspaces (workspace_id, repo_url, last_commit)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                repo_url=excluded.repo_url,
                last_commit=excluded.last_commit
        """, (workspace_id, repo_url, last_commit))

def get_all_workspaces():
    """Retrieves all active workspaces for the UI dashboard."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT workspace_id, repo_url, last_commit FROM workspaces"
        ).fetchall()
        return [{"workspace_id": r[0], "repo_url": r[1], "last_commit": r[2]} for r in rows]

init_db()