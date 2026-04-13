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
from chromadb import EmbeddingFunction, Documents, Embeddings
from dotenv import load_dotenv
from google import genai as google_genai

load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

HANDBOOK_PATH = os.path.join("data", "handbook.md")
VECTOR_STORE_PATH = os.path.join("vector_store")
COLLECTION_NAME = "handbook"
MAX_RESULTS = 1  # number of chunks to retrieve per query

# Sections whose titles match these keywords are kept as one chunk.
# Section 3 — role filter needs full context
# Section 4 — vacation policy spans multiple bullets (entitlement + request process)
# Section 5 — bereavement tiers must be read together
# Section 8 — safety procedures must be read together
KEEP_WHOLE_SECTION_TITLES = [
    "working hours", "attendance",          # Section 3
    "time off", "vacation", "holidays",     # Section 4
    "bereavement", "special leave",         # Section 5
    "safety", "emergency",                  # Section 8
]


# ─────────────────────────────────────────────
# CHROMADB SETUP
# ─────────────────────────────────────────────

class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB-compatible embedding function using google.genai SDK.
    Uses text-embedding-004 — consistent with policy_wellbeing.py approach.
    """
    def __init__(self):
        self._client = google_genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY")
        )

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            text = text.strip() if text else ""
            if not text:
                embeddings.append([0.0] * 3072)
                continue
            result = self._client.models.embed_content(
                model="gemini-embedding-001",
                contents=text
            )
            embeddings.append(result.embeddings[0].values)
        return embeddings


def get_collection():
    """
    Returns the ChromaDB collection using Google's text-embedding-004 model.
    Consistent with policy_wellbeing.py embedding approach.
    Creates the vector_store directory if it does not exist.
    """
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    embedding_fn = GeminiEmbeddingFunction()
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
                if current_section.strip():
                    sections.append({
                        "title": current_title,
                        "content": current_section.strip()
                    })
                current_title = line.replace("#", "").strip()
                current_section = ""
            else:
                current_section += line + "\n"

        if current_section.strip():
            sections.append({
                "title": current_title,
                "content": current_section.strip()
            })

        # Build final chunks — split bullet-point sections into per-bullet chunks
        # EXCEPT sections with role-specific rules (filter_by_role needs the full text)
        chunks = []
        for section in sections:
            title_lower = section["title"].lower()
            keep_whole = any(kw in title_lower for kw in KEEP_WHOLE_SECTION_TITLES)

            if keep_whole:
                # Keep whole section — brain.py filter_by_role() needs all role bullets
                chunks.append(section)
                continue

            # Split into per-bullet chunks for precise retrieval
            bullets = []
            intro_lines = []
            for line in section["content"].split("\n"):
                stripped = line.strip()
                if stripped.startswith("*") or stripped.startswith("-"):
                    bullets.append(stripped)
                elif stripped:
                    intro_lines.append(stripped)

            if not bullets:
                # No bullet points — keep section whole
                chunks.append(section)
                continue

            intro = " ".join(intro_lines)
            for bullet in bullets:
                # Extract bold topic label e.g. "**Kitchen:**" → "Kitchen"
                if "**" in bullet:
                    parts = bullet.split("**")
                    topic = parts[1].rstrip(":") if len(parts) >= 2 else bullet[:40]
                else:
                    topic = bullet.lstrip("*-").strip()[:40]

                bullet_text = bullet.lstrip("*-").strip()
                chunk_content = f"{intro}\n{bullet_text}" if intro else bullet_text

                chunks.append({
                    "title": f"{section['title']} — {topic}",
                    "content": chunk_content
                })

        # Store in ChromaDB
        collection = get_collection()

        # Clear existing data before re-ingesting
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

        # Add chunks to ChromaDB
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk["content"]],
                metadatas=[{"source": chunk["title"]}],
                ids=[f"chunk_{i}"]
            )

        return {
            "success": True,
            "chunks_ingested": len(chunks),
            "message": f"Successfully ingested {len(chunks)} chunks from handbook"
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
        # Auto-ingest if vector store is empty (e.g. first Render deploy)
        collection = get_collection()
        if collection.count() == 0:
            result = ingest_handbook()
            if not result["success"]:
                return {"error": f"Handbook ingestion failed: {result['message']}"}
            collection = get_collection()

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
