"""
policy_handbook.py — GreenLeaf Bot | Policies Tool
================================================
This tool answers HR policy questions using RAG (Retrieval-Augmented Generation).
It reads the GreenLeaf Employee Handbook, stores it in ChromaDB, and retrieves
relevant sections to answer employee questions.

Architecture position (HLD):
    brain.py → policy_handbook.py → ChromaDB (vector_store/)
                    ↓
           returns answer + source section
           never guesses — only answers from handbook

What it handles:
    - Working hours and attendance (Section 3)
    - Time off and vacation (Section 4)
    - Bereavement and special leave (Section 5)
    - Any other section in the handbook

Branch: feature/policy_handbook
"""

import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import chromadb
from chromadb.utils import embedding_functions

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

HANDBOOK_PATH = os.path.join("data", "handbook.md")
VECTOR_STORE_PATH = os.path.join("vector_store")
COLLECTION_NAME = "handbook"
MAX_RESULTS = 1  # number of chunks to retrieve per query


# ─────────────────────────────────────────────
# CHROMADB SETUP
# ─────────────────────────────────────────────

def get_collection():
    """
    Returns the ChromaDB collection.
    Creates the vector_store directory if it does not exist.
    """
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn
    )
    return collection


# ─────────────────────────────────────────────
# INGESTION — run once at setup
# ─────────────────────────────────────────────

def ingest_handbook(path: str = HANDBOOK_PATH) -> dict:
    """
    Reads the GreenLeaf Handbook markdown file, splits it into
    sections, and stores each section in ChromaDB.

    Run this once after cloning the repo:
        python src/tools/policy_handbook.py --ingest

    Args:
        path: path to the handbook markdown file

    Returns:
        {"success": bool, "chunks_ingested": int, "message": str}
    """
    try:
        # Check handbook exists
        if not os.path.exists(path):
            return {
                "success": False,
                "chunks_ingested": 0,
                "message": f"Handbook not found at {path}"
            }

        # Read the handbook
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by markdown headers (## or #)
        sections = []
        current_section = ""
        current_title = "General"

        for line in content.split("\n"):
            if line.startswith("##") or line.startswith("# "):
                # Save previous section
                if current_section.strip():
                    sections.append({
                        "title": current_title,
                        "content": current_section.strip()
                    })
                # Start new section
                current_title = line.replace("#", "").strip()
                current_section = ""
            else:
                current_section += line + "\n"

        # Save last section
        if current_section.strip():
            sections.append({
                "title": current_title,
                "content": current_section.strip()
            })

        # Store in ChromaDB
        collection = get_collection()

        # Clear existing data before re-ingesting
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

        # Add sections to ChromaDB
        for i, section in enumerate(sections):
            collection.add(
                documents=[section["content"]],
                metadatas=[{"source": section["title"]}],
                ids=[f"section_{i}"]
            )

        return {
            "success": True,
            "chunks_ingested": len(sections),
            "message": f"Successfully ingested {len(sections)} sections from handbook"
        }

    except Exception as e:
        return {
            "success": False,
            "chunks_ingested": 0,
            "message": f"Ingestion failed: {str(e)}"
        }


# ─────────────────────────────────────────────
# QUERY — called by brain.py on every policy question
# ─────────────────────────────────────────────

def query_handbook(text: str) -> dict:
    """
    Searches ChromaDB for the most relevant handbook sections
    and returns the answer with source citation.

    Interface contract (do not change):
        Input:  text: str — the employee's question
        Output: {"answer": str, "source": str} or {"error": str}

    Args:
        text: the employee's question

    Returns:
        {"answer": str, "source": str} on success
        {"error": str} on failure
    """
    try:
        # Check vector store has been ingested
        collection = get_collection()
        if collection.count() == 0:
            return {
                "error": "Handbook not loaded. Please run ingestion first."
            }

        # Search ChromaDB
        results = collection.query(
            query_texts=[text],
            n_results=min(MAX_RESULTS, collection.count()),
            include=["documents", "metadatas"]
        )

        # Extract results
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        if not documents:
            return {
                "error": "No relevant information found in the handbook."
            }

        # Return the most relevant chunk
        best_doc = documents[0]
        best_source = metadatas[0].get("source", "GreenLeaf Handbook")

        answer = best_doc
        source = "GreenLeaf Handbook — " + best_source

        return {
            "answer": answer,
            "source": source
        }

    except Exception as e:
        return {
            "error": f"Handbook query failed: {str(e)}"
        }


# ─────────────────────────────────────────────
# ENTRY POINT — run ingestion from command line
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--ingest" in sys.argv:
        print("Ingesting Handbook into ChromaDB...")
        result = ingest_handbook()
        print(f"Result: {result['message']}")
        if result["success"]:
            print(f"Chunks ingested: {result['chunks_ingested']}")
    else:
        print("Usage: python src/tools/policy_handbook.py --ingest")
        print("This ingests the handbook into ChromaDB.")
        print("Run this once after cloning the repo.")


# =============================================================================
# HOW TO USE
# =============================================================================
#
# 1. Install dependencies:
#    pip install chromadb
#
# 2. Ingest the handbook (run once):
#    python src/tools/policy_handbook.py --ingest
#
# 3. Test the queries:
#    python tests/test_policy_handbook.py
#
# Expected results:
#   "When do I have to be in the office?"    → Working hours answer + Section 3
#   "Do I get leave for a family emergency?" → Bereavement answer + Section 5
#   "How many vacation days do I get?"       → 25 days answer + Section 4
#
# =============================================================================
