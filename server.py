# server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.types import Command
import uuid

# Only import the compiled app from main
from main import app

server = FastAPI(title="DevFlow API")

class TaskRequest(BaseModel):
    task: str
    
class FeedbackRequest(BaseModel):
    thread_id: str
    feedback: str

@server.post("/api/start")
async def start_task(request: TaskRequest):
    """Starts a new DevFlow agent run and pauses at human approval."""
    thread_id = str(uuid.uuid4())
    thread = {"configurable": {"thread_id": thread_id}}
    
    # Define the initial state directly here
    state = {
        "task_description": request.task,
        "iterations": 0,
        "max_iterations": 3,
        "files": {},
        "plan": "",
        "test_output": "",
        "status": "in_progress",
        "reviewer_feedback": ""
    }
    
    for output in app.stream(state, thread):
        pass
        
    current_state = app.get_state(thread)
    
    if current_state.tasks and current_state.tasks[0].interrupts:
        interrupt_data = current_state.tasks[0].interrupts[0].value
        return {
            "status": "awaiting_approval",
            "thread_id": thread_id,
            "question": interrupt_data["question"],
            "proposed_files": interrupt_data["files"]
        }
        
    return {"status": "completed", "thread_id": thread_id}

@server.post("/api/feedback")
async def provide_feedback(request: FeedbackRequest):
    """Resumes a paused DevFlow run with human feedback."""
    thread = {"configurable": {"thread_id": request.thread_id}}
    current_state = app.get_state(thread)
    
    if not current_state.tasks or not current_state.tasks[0].interrupts:
        raise HTTPException(status_code=400, detail="No paused task found for this thread.")
        
    for output in app.stream(Command(resume=request.feedback), thread):
        pass
        
    new_state = app.get_state(thread)
    if new_state.tasks and new_state.tasks[0].interrupts:
        interrupt_data = new_state.tasks[0].interrupts[0].value
        return {
            "status": "awaiting_approval",
            "thread_id": request.thread_id,
            "question": interrupt_data["question"],
            "proposed_files": interrupt_data["files"]
        }
        
    return {"status": "completed", "message": "Code successfully approved and saved."}

if __name__ == "__main__":
    import uvicorn
    print("Starting DevFlow Backend on http://localhost:8000")
    uvicorn.run(server, host="0.0.0.0", port=8000)