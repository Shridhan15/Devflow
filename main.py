# main.py
import os
import subprocess
import sys
from typing import TypedDict, Dict
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Load ENV first so Groq initializes properly
load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from agents import planner_node, coder_node, reviewer_node

# ---------------------------------------------------------
# Logging Utilities
# ---------------------------------------------------------
class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    
    @staticmethod
    def agent(name: str):
        print(f"\n{Log.CYAN}{'='*50}\n⚙️  RUNNING NODE: [{name.upper()}]\n{'='*50}{Log.RESET}")

    @staticmethod
    def state_update(key: str, value: str):
        print(f"   {Log.YELLOW}↳ {key}:{Log.RESET} {value[:100]}..." if len(str(value)) > 100 else f"   {Log.YELLOW}↳ {key}:{Log.RESET} {value}")

    @staticmethod
    def success(msg: str):
        print(f"   {Log.GREEN}✓ {msg}{Log.RESET}")
        
    @staticmethod
    def error(msg: str):
        print(f"   {Log.RED}✗ {msg}{Log.RESET}")

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
# 2. Nodes
# ---------------------------------------------------------
# def reader_node(state: dict):
#     Log.agent("reader")
#     repo_path = "dummy_repo"
#     existing_files = {}
    
#     if os.path.exists(repo_path):
#         for filename in os.listdir(repo_path):
#             if filename.endswith(".py"):
#                 filepath = os.path.join(repo_path, filename)
#                 with open(filepath, "r", encoding="utf-8") as f:
#                     existing_files[filename] = f.read()
                    
#     Log.state_update(f"Loaded Files", f"{len(existing_files)} file(s) from {repo_path}")
#     return {"files": existing_files}


# --------------- Reader NODE AST Aware RAG Architecture ---------------
def reader_node(state: dict):
    Log.agent("reader")
    task = state.get("task_description", "")
    
    Log.state_update("Querying DB", "Searching AST-aware vector store for logical structures...")
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    if not os.path.exists("chroma_db"):
        Log.error("chroma_db not found. Did you run ast_indexer.py?")
        return {"files": {}}
        
    vectorstore = Chroma(persist_directory="chroma_db", embedding_function=embeddings)
    
    # Retrieve the top 5 most relevant structural chunks
    retrieved_docs = vectorstore.similarity_search(task, k=5)
    
    relevant_filenames = set()
    retrieved_structures = []
    
    for doc in retrieved_docs:
        filename = doc.metadata.get("filename")
        node_type = doc.metadata.get("node_type", "Unknown")
        node_name = doc.metadata.get("node_name", "Unknown")
        
        if filename:
            relevant_filenames.add(filename)
            # We now know EXACTLY what logical block triggered the match
            retrieved_structures.append(f"[{node_type}: {node_name}]")
            
    if not relevant_filenames:
        Log.error("No relevant structures found in the vector database.")
        return {"files": {}}
        
    # Log the specific architecture it found, removing duplicates
    unique_structures = list(dict.fromkeys(retrieved_structures))
    Log.state_update("AST Match", ", ".join(unique_structures))
    
    # Load the specific files those structures belong to
    repo_path = "dummy_repo"
    loaded_files = {}
    
    for filename in relevant_filenames:
        filepath = os.path.join(repo_path, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                loaded_files[filename] = f.read()
                
    Log.state_update("Loaded Files", f"Injected {len(loaded_files)} file(s) into state.")
    return {"files": loaded_files}

def tester_node(state: dict):
    Log.agent("tester")
    files = state.get("files", {})
    if not files:
        Log.error("No files generated to test.")
        return {"test_output": "No files generated to test.", "status": "failed"}

    repo_path = "dummy_repo"
    os.makedirs(repo_path, exist_ok=True)
    test_filepath = ""
    
    for filename, code_content in files.items():
        filepath = os.path.join(repo_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_content)
        if filename.endswith(".py"):
            test_filepath = filepath
            
    try:
        result = subprocess.run([sys.executable, test_filepath], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            Log.success(f"Execution passed for {filename}")
            return {"test_output": f"Success. Output:\n{result.stdout}", "status": "success"}
        else:
            Log.error(f"Execution crashed. Traceback sent to Coder.")
            return {"test_output": f"Error:\n{result.stderr}", "status": "failed"}
            
    except subprocess.TimeoutExpired:
        Log.error("Execution timed out (infinite loop detected).")
        return {"test_output": "Error: Script execution timed out.", "status": "failed"}


def human_approval_node(state: dict) -> Command:
    Log.agent("human_approval")
    
    # 1. PAUSE: Throw the payload to the terminal and wait
    user_feedback = interrupt({
        "question": "Review the proposed code. Type 'Approve' to accept, or provide feedback for the AI to fix it:",
        "files": state.get("files", {})
    })
    
    # 2. RESUME: Execute this when the user responds
    if user_feedback.lower() in ["approve", "yes", "y", "ok", ""]:
        Log.success("Human approved the changes.")
        return Command(goto=END)
    else:
        Log.error(f"Human rejected with feedback: {user_feedback}")
        new_task = f"{state['task_description']}\n\nHUMAN FEEDBACK TO FIX: {user_feedback}"
        
        # 3. ROUTE: Update state and send back to Planner
        return Command(
            update={"task_description": new_task, "iterations": 0, "status": "in_progress"},
            goto="planner"
        )

# ---------------------------------------------------------
# 3. Standard Routing Logic
# ---------------------------------------------------------
def should_continue(state: dict):
    status = state.get("status")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        return "reviewer"
    if iterations >= max_iterations:
        return END
    return "coder"

def reviewer_router(state: dict):
    status = state.get("status")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        return "human_approval"
    if iterations >= max_iterations:
        return END
    return "coder"

# ---------------------------------------------------------
# 4. Build and Compile the LangGraph
# ---------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("reader", reader_node)
workflow.add_node("planner", planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("tester", tester_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("human_approval", human_approval_node)

workflow.set_entry_point("reader")

workflow.add_edge("reader", "planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "tester")

workflow.add_conditional_edges("tester", should_continue, {"coder": "coder", "reviewer": "reviewer", END: END})
workflow.add_conditional_edges("reviewer", reviewer_router, {"coder": "coder", "human_approval": "human_approval", END: END})

# Checkpointer is required for interrupt() to work
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# ---------------------------------------------------------
# 5. Execution Loop
# ---------------------------------------------------------
# ---------------------------------------------------------
# 5. Execution Loop
# ---------------------------------------------------------
if __name__ == "__main__":
    print(f"\n{Log.GREEN}🚀 Welcome to DevFlow MVP{Log.RESET}")
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
    
    # Thread ID tracks the memory state
    thread = {"configurable": {"thread_id": "session_1"}}
    
    # We use a variable for the input so we can easily swap between 
    # initial_state (first run) and Command(resume=...) (subsequent runs)
    stream_input = initial_state
    
    # NEW: A continuous loop to handle multiple human rejection cycles
    while True:
        # Run the graph until it finishes OR hits an interrupt
        for output in app.stream(stream_input, thread):
            pass
            
        # Detect what state the graph is in now
        current_state = app.get_state(thread)
        
        # If the graph paused for an interrupt, ask the user
        if current_state.tasks and current_state.tasks[0].interrupts:
            interrupt_data = current_state.tasks[0].interrupts[0].value
            
            print(f"\n{Log.YELLOW}{'='*50}")
            print(f"⏸️  {interrupt_data['question']}")
            print(f"{'='*50}{Log.RESET}")
            
            for filename, content in interrupt_data["files"].items():
                print(f"\n{Log.CYAN}--- Proposed {filename} ---{Log.RESET}")
                print(content)
                
            print(f"\n{Log.YELLOW}{'='*50}{Log.RESET}")
            user_input = input("> ")
            
            # Set the input for the next loop iteration to resume the graph
            stream_input = Command(resume=user_input)
            
        else:
            # No interrupts found, meaning the graph reached the END node
            break

    print(f"\n{Log.GREEN}✅ Run complete. Check the 'dummy_repo' directory for the final code.{Log.RESET}")