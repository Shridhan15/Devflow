# ast_indexer.py
import os
import ast
import shutil
import time
import stat
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

print(f"{Log.CYAN}Loading HuggingFace Embeddings into memory...{Log.RESET}")
global_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
print(f"{Log.GREEN}Embeddings loaded successfully.{Log.RESET}")

def extract_ast_chunks(filepath: str, source_code: str):
    # ... (Keep your existing extract_ast_chunks function exactly as is) ...
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
                doc = Document(
                    page_content=chunk_code,
                    metadata={
                        "filename": os.path.basename(filepath),
                        "filepath": filepath,
                        "node_type": type(node).__name__,
                        "node_name": node.name
                    }
                )
                documents.append(doc)
    return documents

def build_ast_index(repo_path="workspaces", persist_dir="chroma_db", changed_files=None):
    print(f"\n{Log.CYAN}--- DEVFLOW AST-AWARE INDEXER ---{Log.RESET}")
    
    if changed_files is None:
        changed_files = ["ALL"]
        
    is_full_index = "ALL" in changed_files

    # 1. Handle Full Index (Wipe Database)
    if is_full_index and os.path.exists(persist_dir):
        print(f"{Log.YELLOW}Performing full re-index. Clearing old database state...{Log.RESET}")
        def on_rm_error(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
        try:
            shutil.rmtree(persist_dir, onerror=on_rm_error)
            time.sleep(0.5)
        except Exception as e:
            print(f"{Log.YELLOW}Warning during DB clear: {e}{Log.RESET}")

    # 2. Connect to Chroma (Creates it if it was wiped/doesn't exist)
    vector_store = Chroma(
        persist_directory=persist_dir,
        embedding_function=global_embeddings
    )

    all_documents = []

    # 3. Handle Incremental Update
    if not is_full_index:
        print(f"{Log.YELLOW}Performing incremental update for {len(changed_files)} file(s)...{Log.RESET}")
        for changed_file in changed_files:
            # Normalize path to match how it was originally saved during os.walk
            target_filepath = os.path.normpath(os.path.join(repo_path, changed_file))
            
            # Step A: Find and delete the old vectors for this specific file
            existing_docs = vector_store.get(where={"filepath": target_filepath})
            if existing_docs and existing_docs["ids"]:
                print(f"Removing {len(existing_docs['ids'])} old vectors for: {target_filepath}")
                vector_store.delete(ids=existing_docs["ids"])
            
            # Step B: Read and parse the newly updated file (if it wasn't deleted)
            if os.path.exists(target_filepath):
                print(f"Parsing updated AST for: {target_filepath}")
                with open(target_filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                ast_docs = extract_ast_chunks(target_filepath, content)
                all_documents.extend(ast_docs)

    # 4. Handle Full Index (Walk Directory)
    else:
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    print(f"Parsing AST for: {filepath}")
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    ast_docs = extract_ast_chunks(filepath, content)
                    all_documents.extend(ast_docs)

    # 5. Insert New/Updated Documents
    if all_documents:
        print(f"\nAdding {len(all_documents)} structural chunks to DB...")
        vector_store.add_documents(documents=all_documents)
        print(f"{Log.GREEN}✅ Codebase structurally indexed into ./{persist_dir}{Log.RESET}")
    elif not is_full_index:
        print(f"{Log.GREEN}✅ Index update complete (no new Python structures).{Log.RESET}")
    else:
        print("No Python structures found to index.")

    return vector_store

if __name__ == "__main__":
    build_ast_index()