# main.py
import os
import subprocess
import sys
import uuid
import sqlite3
from typing import TypedDict, List, Dict

from dotenv import load_dotenv

# Load ENV first so Groq initializes properly
load_dotenv()

from langchain_chroma import Chroma
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

from agents import planner_node, coder_node, reviewer_node
from github_service import sync_workspace, create_pull_request
from ast_indexer import build_ast_index, global_embeddings, get_collection_name


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
    def state_update(key: str, value):
        value = str(value)
        print(f"   {Log.YELLOW}↳ {key}:{Log.RESET} {value[:100]}..." if len(value) > 100
              else f"   {Log.YELLOW}↳ {key}:{Log.RESET} {value}")

    @staticmethod
    def success(msg: str):
        print(f"   {Log.GREEN}✓ {msg}{Log.RESET}")

    @staticmethod
    def error(msg: str):
        print(f"   {Log.RED}✗ {msg}{Log.RESET}")


# ---------------------------------------------------------
# 1. Graph State Schema
#    Every key a node returns MUST be listed here, otherwise LangGraph drops it.
# ---------------------------------------------------------
class AgentState(TypedDict, total=False):
    task_description: str
    repo_url: str
    workspace_path: str
    branch_name: str
    base_commit: str               # commit the feature branch started from (diff baseline)
    iterations: int
    max_iterations: int
    files: dict                    # path -> current content (context + everything edited so far)
    repo_tree: List[str]
    workspace_id: str
    plan: str
    test_output: str
    status: str
    reviewer_feedback: str
    instructions: List[str]        # follow-up instructions the human gave after the first task
    changed_files: List[str]       # files written by the LAST coder attempt (per-attempt)
    deleted_files: List[str]       # accumulated deletions
    affected_files: Dict[str, str] # CUMULATIVE truth from git: path -> added | modified | deleted


# ---------------------------------------------------------
# Path + git helpers
# ---------------------------------------------------------
SKIP_DIRS = {"node_modules", "dist", ".git", "build", ".next"}
CODE_EXTS = (".py", ".js", ".jsx", ".ts", ".tsx", ".css")


def _rel(path: str, repo_path: str) -> str:
    return os.path.relpath(os.path.abspath(path), os.path.abspath(repo_path)).replace("\\", "/")


def _walk_repo(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(CODE_EXTS):
                yield os.path.join(root, name)


def _is_inside(path: str, base: str) -> bool:
    path, base = os.path.abspath(path), os.path.abspath(base)
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:  # different drives on Windows
        return False


def _safe_join(repo_path: str, rel_path: str):
    """Join a model-supplied relative path to the repo, refusing escapes like '../../x'."""
    full = os.path.abspath(os.path.join(repo_path, rel_path))
    return full if _is_inside(full, repo_path) else None


def _git(repo_path: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def get_affected_files(repo_path: str, base_commit: str) -> Dict[str, str]:
    """
    Everything that differs from the commit this branch started at: committed or not,
    tracked or untracked. This is cumulative across ALL coding rounds and is the single
    source of truth for what the UI shows and what the PR will contain.
    """
    if not base_commit:
        return {}
    affected: Dict[str, str] = {}
    tracked = _git(repo_path, "diff", "--name-status", "--no-renames", base_commit)
    for line in tracked.splitlines():
        status, _, path = line.partition("\t")
        if not path:
            continue
        affected[path] = {"A": "added", "D": "deleted"}.get(status[:1], "modified")
    untracked = _git(repo_path, "ls-files", "--others", "--exclude-standard")
    for path in untracked.splitlines():
        if path:
            affected[path] = "added"
    return dict(sorted(affected.items()))


def _write_preserving_eol(path: str, content: str):
    """Keep the file's original line endings so Windows doesn't turn a 3-line edit into a whole-file diff."""
    newline = "\n"
    if os.path.exists(path):
        with open(path, "rb") as f:
            if b"\r\n" in f.read():
                newline = "\r\n"
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(content)


def _review_payload(state: dict) -> dict:
    """What the human sees: only affected files (with content), plus a status map that includes deletions."""
    files = state.get("files", {}) or {}
    affected = state.get("affected_files") or {}
    if not affected:  # git unavailable / nothing recorded: fall back to whatever is in state
        return {"files": files, "file_status": {}}
    return {
        "files": {p: files.get(p, "") for p, s in affected.items() if s != "deleted"},
        "file_status": affected,
    }


# ---------------------------------------------------------
# 2. Nodes
# ---------------------------------------------------------
def setup_node(state: dict):
    Log.agent("setup")
    repo_url = state.get("repo_url")

    branch_name = f"devflow/{str(uuid.uuid4())[:8]}"

    Log.state_update("GitHub", f"Syncing {repo_url} and creating branch {branch_name}")
    workspace_path, changed_files = sync_workspace(repo_url, branch_name)
    workspace_id = os.path.basename(os.path.normpath(workspace_path))

    if changed_files:
        Log.state_update("Indexer", f"Updating AST Vector DB for [{workspace_id}]...")
        build_ast_index(
            repo_path=workspace_path,
            persist_dir="chroma_db",
            changed_files=changed_files,
            workspace_id=workspace_id,
        )
    else:
        Log.success("AST Index is already up-to-date. Skipped.")

    # Diff baseline: the commit this feature branch starts from
    try:
        base_commit = _git(workspace_path, "rev-parse", "HEAD").strip()
        Log.state_update("Base commit", base_commit[:10])
    except Exception as e:
        base_commit = ""
        Log.error(f"Could not record base commit ({e}); affected-file tracking disabled.")

    return {
        "workspace_path": workspace_path,
        "workspace_id": workspace_id,
        "branch_name": branch_name,
        "base_commit": base_commit,
    }

def reader_node(state: dict):
    """
    Runs on the first pass AND again after every human follow-up instruction.
    Retrieval uses the task plus the latest instruction, and new files are MERGED into
    state without overwriting content the Coder has already edited.
    """
    Log.agent("reader")
    task = state.get("task_description", "")
    follow_up = state.get("reviewer_feedback", "") or ""
    query = f"{task}\n{follow_up}".strip()
    repo_path = state.get("workspace_path", "dummy_repo")
    workspace_id = state.get("workspace_id") or os.path.basename(os.path.normpath(repo_path))
    collection_name = get_collection_name(workspace_id)
    existing = dict(state.get("files") or {})

    all_paths = list(_walk_repo(repo_path))
    repo_tree = sorted(_rel(p, repo_path) for p in all_paths)

    Log.state_update("Querying DB", f"Searching isolated collection '{collection_name}'...")

    matched_paths, structures = [], []

    if os.path.exists("chroma_db"):
        vectorstore = Chroma(
            collection_name=collection_name,
            persist_directory="chroma_db",
            embedding_function=global_embeddings,
        )
        for doc in vectorstore.similarity_search(query, k=5):
            fp = doc.metadata.get("filepath")
            if not fp or not _is_inside(fp, repo_path):
                continue
            if fp not in matched_paths:
                matched_paths.append(fp)
            structures.append(f"[{doc.metadata.get('node_type')}: {doc.metadata.get('node_name')}]")
        if structures:
            Log.state_update("AST Match", ", ".join(dict.fromkeys(structures)))
    else:
        Log.error("chroma_db not found. Falling back to keyword search only.")

    # Keyword fallback, also matching adjacent words joined ("love shower" -> LoveShower)
    raw_words = [w.strip(".,:;\"'()").lower() for w in query.replace("-", " ").split()]
    raw_words = [w for w in raw_words if w]
    keywords = {w for w in raw_words if len(w) > 3}
    keywords |= {a + b for a, b in zip(raw_words, raw_words[1:]) if len(a + b) > 5}

    for p in all_paths:
        low = p.lower().replace("_", "").replace("-", "")
        if any(k in low for k in keywords) and p not in matched_paths:
            matched_paths.append(p)

    newly_loaded = {}
    for fp in matched_paths[:10]:
        if not os.path.exists(fp):
            Log.error(f"Reader could not find: {fp}")
            continue
        rel = _rel(fp, repo_path)
        if rel in existing:
            continue  # state already holds the (possibly edited) version: it wins
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            newly_loaded[rel] = f.read()

    merged = {**newly_loaded, **existing}
    Log.state_update("Loaded Files", f"{len(newly_loaded)} new, {len(existing)} already in state: {sorted(merged)}")

    return {"files": merged, "repo_tree": repo_tree}



def tester_node(state: dict):
    Log.agent("tester")
    files = state.get("files", {})
    if not files:
        Log.error("No files generated to test.")
        return {"test_output": "No files generated to test.", "status": "failed"}

    repo_path = state.get("workspace_path", "dummy_repo")
    os.makedirs(repo_path, exist_ok=True)

    # Write only what this attempt changed (earlier rounds are already on disk)
    changed = state.get("changed_files") or list(files)
    written = []
    for filename in changed:
        content = files.get(filename)
        if content is None:
            continue
        filepath = _safe_join(repo_path, filename)
        if not filepath:
            Log.error(f"Refusing to write outside the workspace: {filename}")
            continue
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        _write_preserving_eol(filepath, content)
        written.append(filename)

    for filename in state.get("deleted_files", []):
        filepath = _safe_join(repo_path, filename)
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            Log.state_update("Deleted", filename)

    # Cumulative, git-derived view of everything touched so far in this run
    try:
        affected = get_affected_files(repo_path, state.get("base_commit", ""))
    except Exception as e:
        Log.error(f"Could not compute affected files from git: {e}")
        affected = state.get("affected_files", {})
    Log.state_update("Affected (all rounds)", affected)

    py_files = [f for f in written if f.endswith(".py")]
    if not py_files:
        Log.success("No Python files changed; skipping runtime execution (frontend change).")
        return {"test_output": "Files written. No Python files to execute.",
                "status": "success", "affected_files": affected}

    outputs = []
    for filename in py_files:
        filepath = _safe_join(repo_path, filename)
        try:
            result = subprocess.run(
                [sys.executable, filepath],
                capture_output=True, text=True, timeout=5, cwd=repo_path,
            )
        except subprocess.TimeoutExpired:
            Log.error(f"{filename} timed out (infinite loop detected).")
            return {"test_output": f"Error: {filename} timed out.",
                    "status": "failed", "affected_files": affected}

        if result.returncode != 0:
            Log.error("Execution crashed. Traceback sent to Coder.")
            return {"test_output": f"Error in {filename}:\n{result.stderr}",
                    "status": "failed", "affected_files": affected}

        Log.success(f"Execution passed for {filename}")
        outputs.append(f"{filename}:\n{result.stdout}")

    return {"test_output": "Success. Output:\n" + "\n".join(outputs),
            "status": "success", "affected_files": affected}


def human_code_review_node(state: dict):
    Log.agent("human_code_review")

    payload = _review_payload(state)
    feedback = interrupt({
        "stage": "code_review",
        "question": "AI coding complete. Do you approve these changes or want to request edits?",
        **payload,
    })

    if feedback.strip().lower() == "approve":
        Log.success("Human approved the code modifications.")
        return {"status": "code_approved"}

    Log.error(f"Human requested edits: {feedback}")
    # Fresh iteration budget; remember the instruction for the PR description.
    return {
        "status": "in_progress",
        "reviewer_feedback": feedback,
        "instructions": (state.get("instructions") or []) + [feedback],
        "iterations": 0,
    }


def human_pr_approval_node(state: dict):
    Log.agent("human_pr_approval")

    payload = _review_payload(state)
    feedback = interrupt({
        "stage": "pr_approval",
        "question": f"Ready to push branch '{state.get('branch_name')}' and open a PR on GitHub. Proceed?",
        **payload,
    })

    if feedback.strip().lower() == "approve":
        Log.success("Human authorized GitHub PR creation.")
        return {"status": "pr_approved"}

    Log.error("Human aborted the PR process.")
    return {"status": "pr_aborted"}


def pr_node(state: dict):
    Log.agent("github_pr")
    repo_url = state.get("repo_url")
    branch_name = state.get("branch_name")
    task = state.get("task_description")

    repo_name = "/".join(repo_url.replace(".git", "").split("/")[-2:])

    affected = state.get("affected_files") or {}
    file_lines = "\n".join(f"- `{p}` ({s})" for p, s in affected.items()) or "_(not tracked)_"
    instructions = state.get("instructions") or []
    follow_ups = "".join(f"\n{i}. {text}" for i, text in enumerate(instructions, 1))

    body = f"Automated changes generated by DevFlow.\n\n**Task:** {task}\n"
    if follow_ups:
        body += f"\n**Follow-up instructions:**{follow_ups}\n"
    body += f"\n**Files changed ({len(affected)}):**\n{file_lines}"

    Log.state_update("GitHub", f"Pushing branch and creating PR for {repo_name}")
    pr_url = create_pull_request(
        repo_name=repo_name,
        branch_name=branch_name,
        title=f"DevFlow: {task[:50]}...",
        body=body,
    )

    Log.state_update("Success", f"Pull Request opened: {pr_url}")
    return {"status": "completed"}


# ---------------------------------------------------------
# 3. Routing Logic
# ---------------------------------------------------------
def coder_routing(state: dict):
    """Stop burning iterations when the coder produced nothing."""
    status = state.get("status")
    if status == "no_context":
        return END
    if status == "coder_failed":
        if state.get("iterations", 0) >= state.get("max_iterations", 3):
            return END
        return "planner"
    return "tester"


def ai_review_routing(state: dict):
    status = state.get("status", "").lower()
    if status in ["approved", "pass", "passed", "success"] or \
            state.get("iterations", 0) >= state.get("max_iterations", 3):
        return "human_code_review"
    return "planner"


def human_code_routing(state: dict):
    if state.get("status") == "code_approved":
        return "human_pr_approval"
    # A follow-up instruction may concern files the first search never loaded,
    # so go back through the Reader (merge-safe) before planning.
    return "reader"


def human_pr_routing(state: dict):
    if state.get("status") == "pr_approved":
        return "pr_node"
    return END


# ---------------------------------------------------------
# 4. Graph Compilation
# ---------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("setup", setup_node)
workflow.add_node("reader", reader_node)
workflow.add_node("planner", planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("tester", tester_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("human_code_review", human_code_review_node)
workflow.add_node("human_pr_approval", human_pr_approval_node)
workflow.add_node("pr_node", pr_node)

workflow.set_entry_point("setup")
workflow.add_edge("setup", "reader")
workflow.add_edge("reader", "planner")
workflow.add_edge("planner", "coder")
workflow.add_conditional_edges("coder", coder_routing)
workflow.add_edge("tester", "reviewer")
workflow.add_conditional_edges("reviewer", ai_review_routing)
workflow.add_conditional_edges("human_code_review", human_code_routing)
workflow.add_conditional_edges("human_pr_approval", human_pr_routing)
workflow.add_edge("pr_node", END)

conn = sqlite3.connect("devflow_state.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)
app = workflow.compile(checkpointer=memory)


# ---------------------------------------------------------
# 5. Execution Loop (CLI)
# ---------------------------------------------------------
if __name__ == "__main__":
    print(f"\n{Log.GREEN}🚀 Welcome to DevFlow MVP{Log.RESET}")
    repo_url = input("GitHub repo URL (blank = REPO_URL env var):\n> ").strip() or os.getenv("REPO_URL", "")
    if not repo_url:
        raise SystemExit("A repo URL is required (enter it or set REPO_URL).")
    user_task = input("What would you like me to build or change?\n> ")

    initial_state = {
        "task_description": user_task,
        "repo_url": repo_url,
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

    thread = {"configurable": {"thread_id": f"session_{uuid.uuid4().hex[:8]}"}}
    stream_input = initial_state

    while True:
        for _ in app.stream(stream_input, thread):
            pass

        current_state = app.get_state(thread)

        if current_state.tasks and current_state.tasks[0].interrupts:
            interrupt_data = current_state.tasks[0].interrupts[0].value

            print(f"\n{Log.YELLOW}{'='*50}")
            print(f"⏸️  {interrupt_data['question']}")
            print(f"{'='*50}{Log.RESET}")

            status_map = interrupt_data.get("file_status", {})
            for path, st in status_map.items():
                print(f"   [{st}] {path}")
            for filename, content in interrupt_data["files"].items():
                print(f"\n{Log.CYAN}--- {filename} ---{Log.RESET}")
                print(content)

            print(f"\n{Log.YELLOW}{'='*50}{Log.RESET}")
            user_input = input("> ")
            stream_input = Command(resume=user_input)
        else:
            break

    final = current_state.values
    status = final.get("status")
    if status == "completed":
        print(f"\n{Log.GREEN}✅ Run complete. Pull request opened from branch {final.get('branch_name')}.{Log.RESET}")
    elif status in ("coder_failed", "no_context"):
        print(f"\n{Log.RED}❌ Run stopped: the coder could not produce changes ({status}).{Log.RESET}")
    else:
        print(f"\n{Log.GREEN}✅ Run finished (status: {status}). Check '{final.get('workspace_path')}' for the code.{Log.RESET}")