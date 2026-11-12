# indexer.py
import os
import shutil
import time
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

def build_index(repo_path="dummy_repo", persist_dir="chroma_db"):
    print(f"\n{Log.CYAN}--- DEVFLOW CODEBASE INDEXER ---{Log.RESET}")
    
    # NEW: Safely wipe the existing database to prevent chunk duplication
    if os.path.exists(persist_dir):
        print(f"{Log.YELLOW}Clearing old database state...{Log.RESET}")
        
        # Chroma sometimes locks the SQLite file, so we force-close references
        # and delete the directory to ensure a perfectly clean slate.
        try:
            shutil.rmtree(persist_dir)
            time.sleep(0.5) # Brief pause to let the OS release file locks
        except Exception as e:
            print(f"Warning: Could not completely clear DB due to file lock: {e}")

    print(f"Scanning repository: {repo_path}")
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    python_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON,
        chunk_size=1500,
        chunk_overlap=200
    )
    
    documents = []
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                print(f"Reading: {filepath}")
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                chunks = python_splitter.create_documents(
                    texts=[content], 
                    metadatas=[{"source": filepath, "filename": file}]
                )
                documents.extend(chunks)
                
    if not documents:
        print("No Python files found to index.")
        return
        
    print(f"\nCreated {len(documents)} logical chunks. Building Vector Database...")
    
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_dir
    )
    
    print(f"{Log.GREEN}✅ Codebase successfully indexed (Clean Sync) into ./{persist_dir}{Log.RESET}")

if __name__ == "__main__":
    build_index()