# server.py
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command

from workspace_db import get_all_workspaces

# Only import the compiled app from main
from main import app

server = FastAPI(title="DevFlow API")
server.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str
    repo_url: str


class FeedbackRequest(BaseModel):
    thread_id: str
    feedback: str


def _build_response(thread_id: str) -> dict:
    """Inspect the graph after a run/resume and describe where it ended up."""
    thread = {"configurable": {"thread_id": thread_id}}
    state = app.get_state(thread)

    # Paused at a human gate
    if state.tasks and state.tasks[0].interrupts:
        data = state.tasks[0].interrupts[0].value
        return {
            "status": "awaiting_approval",
            "thread_id": thread_id,
            "stage": data.get("stage"),  # "code_review" or "pr_approval"
            "question": data["question"],
            "proposed_files": data["files"],
            "file_status": data.get("file_status", {}),  # path -> added | modified | deleted
        }

    # Graph finished: report what actually happened
    values = state.values or {}
    final_status = values.get("status")

    if final_status == "completed":
        return {
            "status": "completed",
            "thread_id": thread_id,
            "branch_name": values.get("branch_name"),
            "message": "Task finished and Pull Request created!",
        }

    if final_status == "pr_aborted":
        return {
            "status": "aborted",
            "thread_id": thread_id,
            "message": "PR creation was cancelled. No pull request was opened.",
        }

    # coder_failed / no_context / anything else that ended the run early
    return {
        "status": "failed",
        "thread_id": thread_id,
        "agent_status": final_status,
        "message": values.get("reviewer_feedback")
        or "The agent could not produce any code changes for this task.",
    }


# Plain `def` (not `async def`): app.stream() is blocking, so FastAPI runs
# these in its threadpool instead of freezing the event loop.
@server.post("/api/start")
def start_task(request: TaskRequest):
    """Starts a new DevFlow agent run on a specific GitHub repository."""
    thread_id = str(uuid.uuid4())
    thread = {"configurable": {"thread_id": thread_id}}

    state = {
        "task_description": request.task,
        "repo_url": request.repo_url,
        "iterations": 0,
        "max_iterations": 3,
        "files": {},
        "repo_tree": [],
        "plan": "",
        "test_output": "",
        "status": "in_progress",
        "reviewer_feedback": "",
        "instructions": [],
        "changed_files": [],
        "deleted_files": [],
        "affected_files": {},
    }

    try:
        for _ in app.stream(state, thread):
            pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")

    return _build_response(thread_id)


@server.post("/api/feedback")
def provide_feedback(request: FeedbackRequest):
    """Resumes a paused DevFlow run with human feedback."""
    thread = {"configurable": {"thread_id": request.thread_id}}
    current_state = app.get_state(thread)

    if not current_state.tasks or not current_state.tasks[0].interrupts:
        raise HTTPException(status_code=400, detail="No paused task found for this thread.")

    try:
        for _ in app.stream(Command(resume=request.feedback), thread):
            pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")

    return _build_response(request.thread_id)


@server.get("/api/workspaces")
def fetch_workspaces():
    """Returns a list of all persistent workspaces."""
    return get_all_workspaces()


if __name__ == "__main__":
    import uvicorn
    print("Starting DevFlow Backend on http://localhost:8000")
    uvicorn.run(server, host="0.0.0.0", port=8000)