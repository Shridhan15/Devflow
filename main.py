# main.py
import os
import sys
import subprocess
from typing import TypedDict, Dict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# Import the agent nodes we just built
from agents import planner_node, coder_node

# Load environment variables (GROQ_API_KEY)
load_dotenv()

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

# ---------------------------------------------------------
# 2. Define the Tester Node
# ---------------------------------------------------------
def tester_node(state: dict):
    """Executes the written code locally and captures the output/errors."""
    print("--- TESTER AGENT RUNNING ---")
    
    files = state.get("files", {})
    if not files:
        return {"test_output": "No files generated to test.", "status": "failed"}

    # For the MVP, we assume the Coder generates one main Python file.
    # We grab the first filename and its code content.
    filename = list(files.keys())[0]
    code_content = files[filename]
    
    # Secure a path in the workspace directory
    filepath = os.path.join("workspace", filename)
    
    # Write the AI-generated code to the local disk
    # Write the AI-generated code to the local disk using UTF-8
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code_content)
        
    print(f"Executing {filepath} locally...")
    
    try:
        # Run the script with a strict 5-second timeout to prevent infinite loops
        result = subprocess.run(
            [sys.executable, filepath], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        if result.returncode == 0:
            print("Execution successful!")
            return {
                "test_output": f"Success. Output:\n{result.stdout}",
                "status": "success"
            }
        else:
            print(f"Execution failed with return code {result.returncode}.")
            return {
                "test_output": f"Error:\n{result.stderr}",
                "status": "failed"
            }
            
    except subprocess.TimeoutExpired:
        print("Execution timed out.")
        return {
            "test_output": "Error: Script execution timed out after 5 seconds. You may have an infinite loop.",
            "status": "failed"
        }

# ---------------------------------------------------------
# 3. Define Routing Logic (Conditional Edges)
# ---------------------------------------------------------
def should_continue(state: dict):
    """Determines whether to loop back to the coder or end the graph."""
    status = state.get("status")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        print("-> Routing to END (Tests Passed)")
        return END
    
    if iterations >= max_iterations:
        print(f"-> Routing to END (Max iterations {max_iterations} reached. Task failed.)")
        return END
        
    print(f"-> Routing back to CODER (Attempt {iterations + 1}/{max_iterations})")
    return "coder"

# ---------------------------------------------------------
# 4. Build and Compile the LangGraph
# ---------------------------------------------------------
workflow = StateGraph(AgentState)

# Add our nodes
workflow.add_node("planner", planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("tester", tester_node)

# Set the entry point
workflow.set_entry_point("planner")

# Add linear edges
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "tester")

# Add the conditional edge for the debugging loop
workflow.add_conditional_edges(
    "tester",
    should_continue,
    {
        "coder": "coder",
        END: END
    }
)

# Compile the graph into a runnable application
app = workflow.compile()

# ---------------------------------------------------------
# 5. Run the Application
# ---------------------------------------------------------
if __name__ == "__main__":
    print("\n🚀 Welcome to DevFlow MVP")
    user_task = input("What would you like me to build? (e.g., 'Write a python script that prints the first 10 Fibonacci numbers'):\n> ")
    
    initial_state = {
        "task_description": user_task,
        "iterations": 0,
        "max_iterations": 3,
        "files": {},
        "plan": "",
        "test_output": "",
        "status": "in_progress"
    }
    
    # main.py (bottom section)
    print("\nStarting autonomous agent loop...\n")
    
    for output in app.stream(initial_state):
        for node_name, state_update in output.items():
            print(f"\n{'='*50}")
            print(f"Update from node: [{node_name.upper()}]")
            print(f"{'='*50}")
            
            # Print exactly what this node updated in the state
            for key, value in state_update.items():
                print(f"{key}: {value}")
            
    print("\n✅ Run complete. Check the 'workspace' directory for the final code.")

