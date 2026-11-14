# github_service.py
import os
import shutil # NEW IMPORT
from git import Repo
from github import Github
from dotenv import load_dotenv
from workspace_db import get_workspace, update_workspace

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

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def sync_workspace(repo_url: str, branch_name: str, workspace_dir: str = "workspaces"):
    """Smart syncs the repo, calculates file deltas, and creates a feature branch."""
    os.makedirs(workspace_dir, exist_ok=True)
    
    # Use the repository name as the unique workspace ID
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    workspace_id = repo_name
    local_path = os.path.join(workspace_dir, repo_name)
    
    ws_data = get_workspace(workspace_id)
    last_commit = ws_data["last_commit"] if ws_data else None
    changed_files = []
    
    if not os.path.exists(local_path):
        Log.state_update("Git", f"Fresh workspace. Cloning {repo_url}...")
        repo = Repo.clone_from(repo_url, local_path)
        new_commit = repo.head.commit.hexsha
        changed_files = ["ALL"] # Flag to index the entire codebase
    else:
        Log.state_update("Git", f"Workspace exists. Performing hard sync on {workspace_id}...")
        repo = Repo(local_path)
        
        # 1. Force wipe any dirty files or uncommitted AI changes
        repo.git.reset('--hard')
        repo.git.clean('-fd')
        
        # 2. Switch back to main and pull latest remote changes
        if 'main' in repo.heads:
            repo.heads.main.checkout()
        else:
            repo.git.checkout('main')
            
        repo.remotes.origin.fetch()
        repo.git.reset('--hard', 'origin/main')
        
        new_commit = repo.head.commit.hexsha
        
        # 3. Calculate file delta
        if last_commit and last_commit != new_commit:
            diff_output = repo.git.diff('--name-only', last_commit, new_commit)
            if diff_output:
                # Keep only .py files that changed
                changed_files = [f for f in diff_output.split('\n') if f.endswith('.py')]
                Log.state_update("Delta", f"{len(changed_files)} file(s) changed since last run.")
        elif last_commit == new_commit:
            Log.state_update("Delta", "No upstream changes. Skipping AST Indexer.")
            changed_files = [] # Empty list means skip indexing
            
    # Save the new commit hash to the database
    update_workspace(workspace_id, repo_url, new_commit)
    
    # Checkout the isolated feature branch for the agent
    Log.state_update("Branch", f"Checking out feature branch: {branch_name}")
    repo.git.checkout('-b', branch_name)
    
    return local_path, changed_files

def create_pull_request(repo_name: str, branch_name: str, title: str, body: str):
    """Commits changes, pushes the branch, and opens a Pull Request via GitHub API."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is missing in the .env file.")
        
    # 1. Commit and Push locally using GitPython
    local_path = os.path.join("workspaces", repo_name.split("/")[-1])
    repo = Repo(local_path)
    
    repo.git.add(A=True)
    repo.index.commit(f"DevFlow: {title}")
    
    print(f"{Log.CYAN}Pushing branch {branch_name} to origin...{Log.RESET}")
    # Push using the token in the URL for authentication
    origin = repo.remote(name='origin')
    origin_url = origin.url.replace("https://", f"https://{GITHUB_TOKEN}@")
    repo.git.push(origin_url, branch_name, set_upstream=True)
    
    # 2. Open the PR using PyGithub
    print(f"{Log.CYAN}Opening Pull Request on GitHub...{Log.RESET}")
    g = Github(GITHUB_TOKEN)
    gh_repo = g.get_repo(repo_name) # Format must be "username/repository"
    
    pr = gh_repo.create_pull(
        title=title,
        body=body,
        head=branch_name,
        base="main"
    )
    
    print(f"{Log.GREEN}✅ Pull Request Created: {pr.html_url}{Log.RESET}")
    return pr.html_url