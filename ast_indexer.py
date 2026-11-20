# ast_indexer.py
import os
import re
import ast
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

SUPPORTED_FRONTEND_EXTS = (".js", ".jsx", ".ts", ".tsx", ".css")
IGNORED_DIRS = {"node_modules", "dist", "build", ".git", "venv", ".venv", "__pycache__"}

print(f"{Log.CYAN}Loading HuggingFace Embeddings into memory...{Log.RESET}")
global_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
print(f"{Log.GREEN}Embeddings loaded successfully.{Log.RESET}")


def get_collection_name(workspace_id: str) -> str:
    """Converts a workspace_id into a valid ChromaDB collection name (3-63 chars)."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", workspace_id or "").strip("_-")
    name = f"ws_{sanitized}" if sanitized else "ws_default"
    return name[:63].rstrip("_-")


def extract_frontend_chunks(filepath: str, source_code: str):
    """Chunks JS/JSX/TS/TSX/CSS files using syntax-aware text splitting."""
    splitter = RecursiveCharacterTextSplitter.from_language(
        language="js",
        chunk_size=1500,
        chunk_overlap=150
    )
    chunks = splitter.split_text(source_code)
    documents = []

    for i, chunk in enumerate(chunks):
        documents.append(Document(
            page_content=chunk,
            metadata={
                "filename": os.path.basename(filepath),
                "filepath": filepath,
                "node_type": "FrontendChunk",
                "node_name": f"chunk_{i}"
            }
        ))
    return documents


def extract_ast_chunks(filepath: str, source_code: str):
    """Parses Python code into an AST and extracts distinct functions and classes."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"{Log.YELLOW}Syntax error in {filepath}: {e}{Log.RESET}")
        return []

    documents = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chunk_code = ast.get_source_segment(source_code, node)
            if chunk_code:
                documents.append(Document(
                    page_content=chunk_code,
                    metadata={
                        "filename": os.path.basename(filepath),
                        "filepath": filepath,
                        "node_type": type(node).__name__,
                        "node_name": node.name
                    }
                ))
    return documents


def parse_file_to_docs(filepath: str):
    """Routes a file to the right parser based on extension."""
    norm_path = os.path.normpath(filepath)

    if norm_path.endswith(".py"):
        print(f"Parsing Python AST for: {norm_path}")
        with open(norm_path, "r", encoding="utf-8", errors="ignore") as f:
            return extract_ast_chunks(norm_path, f.read())

    if norm_path.endswith(SUPPORTED_FRONTEND_EXTS):
        print(f"Parsing Frontend Code for: {norm_path}")
        with open(norm_path, "r", encoding="utf-8", errors="ignore") as f:
            return extract_frontend_chunks(norm_path, f.read())

    return []


def build_ast_index(
    repo_path="workspaces",
    persist_dir="chroma_db",
    changed_files=None,
    workspace_id=None
):
    # Derive workspace_id from folder name if not explicitly passed
    ws_id = workspace_id or os.path.basename(os.path.normpath(repo_path))
    collection_name = get_collection_name(ws_id)

    print(f"\n{Log.CYAN}--- DEVFLOW AST-AWARE INDEXER [{collection_name}] ---{Log.RESET}")

    if changed_files is None:
        changed_files = ["ALL"]

    is_full_index = "ALL" in changed_files

    # 1. Connect to this workspace's isolated collection
    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=persist_dir,
        embedding_function=global_embeddings
    )

    # 2. If full re-index, reset ONLY this workspace's collection (leaves other repos intact)
    if is_full_index:
        print(f"{Log.YELLOW}Performing full re-index. Resetting collection '{collection_name}'...{Log.RESET}")
        vector_store.delete_collection()
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=persist_dir,
            embedding_function=global_embeddings
        )

    all_documents = []

    # 3. Incremental Update
    if not is_full_index:
        print(f"{Log.YELLOW}Performing incremental update for {len(changed_files)} file(s)...{Log.RESET}")
        for changed_file in changed_files:
            target_filepath = os.path.normpath(os.path.join(repo_path, changed_file))

            # Remove old vectors for this specific file
            existing_docs = vector_store.get(where={"filepath": target_filepath})
            if existing_docs and existing_docs["ids"]:
                print(f"Removing {len(existing_docs['ids'])} old vectors for: {target_filepath}")
                vector_store.delete(ids=existing_docs["ids"])

            # Parse updated file if it still exists
            if os.path.exists(target_filepath):
                all_documents.extend(parse_file_to_docs(target_filepath))

    # 4. Full Index (Walk Directory)
    else:
        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place so os.walk never even enters them
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                filepath = os.path.join(root, file)
                all_documents.extend(parse_file_to_docs(filepath))

    # 5. Insert New/Updated Documents
    if all_documents:
        print(f"\nAdding {len(all_documents)} chunks to collection '{collection_name}'...")
        vector_store.add_documents(documents=all_documents)
        print(f"{Log.GREEN}✅ Codebase indexed into ./{persist_dir} [{collection_name}]{Log.RESET}")
    elif not is_full_index:
        print(f"{Log.GREEN}✅ Incremental update complete (no new chunks).{Log.RESET}")
    else:
        print("No supported source files found to index.")

    return vector_store