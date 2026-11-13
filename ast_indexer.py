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

# 1. INITIALIZE ONCE AT STARTUP (Global Scope)
print(f"{Log.CYAN}Loading HuggingFace Embeddings into memory...{Log.RESET}")
global_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
print(f"{Log.GREEN}Embeddings loaded successfully.{Log.RESET}")

def extract_ast_chunks(filepath: str, source_code: str):
    """Parses Python code into an AST and extracts distinct functions and classes."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"{Log.YELLOW}Syntax error in {filepath}: {e}{Log.RESET}")
        return []

    documents = []
    
    # Traverse the syntax tree
    for node in ast.walk(tree):
        # We only care about entire Classes or Functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Extract the exact, unbroken raw string of this specific node
            chunk_code = ast.get_source_segment(source_code, node)
            
            if chunk_code:
                # Create a LangChain Document with rich structural metadata
                doc = Document(
                    page_content=chunk_code,
                    metadata={
                        "filename": os.path.basename(filepath),
                        "filepath": filepath,
                        "node_type": type(node).__name__, # e.g., 'ClassDef' or 'FunctionDef'
                        "node_name": node.name            # e.g., 'UserManager' or 'add_user'
                    }
                )
                documents.append(doc)
                
    return documents

def build_ast_index(repo_path="workspaces", persist_dir="chroma_db"):
    print(f"\n{Log.CYAN}--- DEVFLOW AST-AWARE INDEXER ---{Log.RESET}")
    
    if os.path.exists(persist_dir):
        print(f"{Log.YELLOW}Clearing old database state...{Log.RESET}")
        
        # 2. Add error handling for Windows file locks
        def on_rm_error(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            
        try:
            shutil.rmtree(persist_dir, onerror=on_rm_error)
            time.sleep(0.5)
        except Exception as e:
            print(f"{Log.YELLOW}Warning during DB clear: {e}{Log.RESET}")

    all_documents = []
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                print(f"Parsing AST for: {filepath}")
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Use our custom AST chunker instead of the character splitter
                ast_docs = extract_ast_chunks(filepath, content)
                all_documents.extend(ast_docs)
                
                for doc in ast_docs:
                    print(f"  -> Extracted {doc.metadata['node_type']}: {doc.metadata['node_name']}")

    if not all_documents:
        print("No Python structures found to index.")
        return
        
    print(f"\nBuilding Vector Database with {len(all_documents)} structural chunks...")
    
    # 3. Use the pre-loaded global model instead of initializing a new one
    Chroma.from_documents(
        documents=all_documents,
        embedding=global_embeddings,
        persist_directory=persist_dir
    )
    
    print(f"{Log.GREEN}✅ Codebase structurally indexed into ./{persist_dir}{Log.RESET}")

if __name__ == "__main__":
    build_ast_index()