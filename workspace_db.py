# workspace_db.py
import sqlite3
import os

DB_PATH = "workspaces_state.sqlite"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                repo_url TEXT NOT NULL,
                last_commit TEXT
            )
        """)

def get_workspace(workspace_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT repo_url, last_commit FROM workspaces WHERE workspace_id = ?", 
            (workspace_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"repo_url": row[0], "last_commit": row[1]}
        return None

def update_workspace(workspace_id: str, repo_url: str, last_commit: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO workspaces (workspace_id, repo_url, last_commit)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                repo_url=excluded.repo_url,
                last_commit=excluded.last_commit
        """, (workspace_id, repo_url, last_commit))

def get_all_workspaces():
    """Retrieves all active workspaces for the UI dashboard."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT workspace_id, repo_url, last_commit FROM workspaces")
        rows = cursor.fetchall()
        return [{"workspace_id": r[0], "repo_url": r[1], "last_commit": r[2]} for r in rows]

# Auto-initialize table on import
init_db()