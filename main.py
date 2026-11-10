# main.py
import os
import subprocess
import sys
from typing import TypedDict, Dict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
load_dotenv()

# Import all agent nodes
from agents import planner_node, coder_node, reviewer_node

# Load environment variables

# ---------------------------------------------------------
# 1. Define the Graph State Schema
# ---------------------------------------------------------
class AgentState(TypedDict):
    task_description: str
    plan: str
    files: Dict[str, str]
    test_output: str
    iterations: int
    max_iterations: int
    status: str
    reviewer_feedback: str

# ---------------------------------------------------------
# 2. NEW: Define the Reader Node
# ---------------------------------------------------------
def reader_node(state: dict):
    """Scans the dummy_repo and loads existing files into the state."""
    print("--- READER AGENT RUNNING ---")
    repo_path = "dummy_repo"
    existing_files = {}
    
    # Read all python files currently in the dummy_repo
    if os.path.exists(repo_path):
        for filename in os.listdir(repo_path):
            if filename.endswith(".py"):
                filepath = os.path.join(repo_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_files[filename] = f.read()
                    
    print(f"Loaded {len(existing_files)} file(s) from {repo_path}.")
    
    # Inject the existing code into the LangGraph state
    return {"files": existing_files}

# ---------------------------------------------------------
# 3. Define the Tester Node
# ---------------------------------------------------------
def tester_node(state: dict):
    """Executes the code locally and captures the output/errors."""
    print("--- TESTER AGENT RUNNING ---")
    
    files = state.get("files", {})
    if not files:
        return {"test_output": "No files generated to test.", "status": "failed"}

    repo_path = "dummy_repo"
    os.makedirs(repo_path, exist_ok=True)
    
    test_filepath = ""
    
    # Write the AI's updated code back into the dummy_repo
    for filename, code_content in files.items():
        filepath = os.path.join(repo_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_content)
            
        # We will attempt to run whatever .py file we find
        if filename.endswith(".py"):
            test_filepath = filepath
            
    print(f"Executing {test_filepath} locally...")
    
    try:
        result = subprocess.run(
            [sys.executable, test_filepath], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        if result.returncode == 0:
            print("Execution successful!")
            return {"test_output": f"Success. Output:\n{result.stdout}", "status": "success"}
        else:
            print(f"Execution failed with return code {result.returncode}.")
            return {"test_output": f"Error:\n{result.stderr}", "status": "failed"}
            
    except subprocess.TimeoutExpired:
        print("Execution timed out.")
        return {"test_output": "Error: Script execution timed out.", "status": "failed"}

# ---------------------------------------------------------
# 4. Define Routing Logic (Conditional Edges)
# ---------------------------------------------------------
def should_continue(state: dict):
    status = state.get("status")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        print("-> Routing to REVIEWER (Tests Passed)")
        return "reviewer"
    
    if iterations >= max_iterations:
        print(f"-> Routing to END (Max iterations {max_iterations} reached. Task failed.)")
        return END
        
    print(f"-> Routing back to CODER (Attempt {iterations + 1}/{max_iterations})")
    return "coder"

def reviewer_router(state: dict):
    status = state.get("status")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        print("-> Routing to END (Code Approved)")
        return END
        
    if iterations >= max_iterations:
        print(f"-> Routing to END (Max iterations {max_iterations} reached. Review failed.)")
        return END
        
    print("-> Routing back to CODER (Code Rejected by Reviewer)")
    return "coder"

# ---------------------------------------------------------
# 5. Build and Compile the LangGraph
# ---------------------------------------------------------
workflow = StateGraph(AgentState)

# Add our nodes
workflow.add_node("reader", reader_node)
workflow.add_node("planner", planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("tester", tester_node)
workflow.add_node("reviewer", reviewer_node)

# NEW: The graph now starts with the reader!
workflow.set_entry_point("reader")

# Add linear edges
workflow.add_edge("reader", "planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "tester")

# Add conditional edges
workflow.add_conditional_edges("tester", should_continue, {"coder": "coder", "reviewer": "reviewer", END: END})
workflow.add_conditional_edges("reviewer", reviewer_router, {"coder": "coder", END: END})

# Compile the graph
app = workflow.compile()

# ---------------------------------------------------------
# 6. Run the Application
# ---------------------------------------------------------
if __name__ == "__main__":
    print("\n🚀 Welcome to DevFlow MVP")
    user_task = input("What would you like me to build or change?\n> ")
    
    initial_state = {
        "task_description": user_task,
        "iterations": 0,
        "max_iterations": 3,
        "files": {},
        "plan": "",
        "test_output": "",
        "status": "in_progress",
        "reviewer_feedback": ""
    }
    
    print("\nStarting autonomous agent loop...\n")
    for output in app.stream(initial_state):
        pass
        
    print("\n✅ Run complete. Check the 'dummy_repo' directory for the final code.")