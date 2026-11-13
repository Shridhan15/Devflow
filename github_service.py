# github_service.py
import os
import shutil # NEW IMPORT
from git import Repo
from github import Github
from dotenv import load_dotenv

class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def clone_and_branch(repo_url: str, branch_name: str, workspace_dir: str = "workspaces") -> str:
    """Clones a repository and checks out a new feature branch."""
    os.makedirs(workspace_dir, exist_ok=True)
    
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    local_path = os.path.join(workspace_dir, repo_name)
    
    # ENFORCE CLEAN SLATE: If a dirty workspace exists from a crashed run, nuke it.
    if os.path.exists(local_path):
        print(f"{Log.YELLOW}Found old workspace. Wiping it to ensure a clean clone...{Log.RESET}")
        # Need to handle Git's read-only files on Windows during deletion
        def on_rm_error(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            
        shutil.rmtree(local_path, onerror=on_rm_error)
        
    print(f"{Log.CYAN}Cloning fresh copy of {repo_url} into {local_path}...{Log.RESET}")
    repo = Repo.clone_from(repo_url, local_path)
        
    print(f"{Log.CYAN}Creating and checking out branch: {branch_name}{Log.RESET}")
    repo.git.checkout('-b', branch_name)
    
    return local_path

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