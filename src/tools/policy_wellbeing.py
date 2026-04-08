"""
policy_wellbeing.py — GreenLeaf Bot | Hooman's RAG Policy/Wellbeing Tool
========================================================================
Purpose:
- Solves Issue #42 and #43 with minimal impact on teammates' code
- Loads and indexes the whole data/ folder (all .md files)
- Answers ONLY from provided internal text
- Redirects sensitive matters (harassment / bullying / whistleblowing)
  to ombudsman@greenleaf-safety.ch
- Returns answer + source for app.py / brain.py

Important:
This file is intentionally separate from policy_tool.py to make merge easier.
"""

# >>> HOOMAN START
import os
import sys
from typing import List, Tuple

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
import google.generativeai as genai

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

VECTORSTORE = None

SENSITIVE_KEYWORDS = [
    "harassment",
    "bullying",
    "whistleblowing",
    "misconduct",
    "abuse",
    "threat",
    "unsafe",
    "discrimination",
    "sexual harassment",
    "hostile workplace",
]

OMBUDSMAN_EMAIL = "ombudsman@greenleaf-safety.ch"


# -------------------------------------------------
# STEP 1 — LOAD ALL .md FILES FROM data/
# -------------------------------------------------

def load_all_documents(folder_path: str = DATA_DIR) -> List[Tuple[str, str]]:
    """
    Loads all markdown files from data/ folder.

    Returns:
        List of tuples: (filename, content)

    Why this exists:
    Issue #43 explicitly says:
    'Write the Python logic to load and index the data/ folder'
    So we do not load only handbook.md — we load all .md files in data/.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Data folder not found: {folder_path}")

    documents = []

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path) and filename.endswith(".md"):
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if content:
                    documents.append((filename, content))

    if not documents:
        raise ValueError("No .md files found in the data folder.")

    return documents


# -------------------------------------------------
# STEP 2 — BUILD VECTOR STORE
# -------------------------------------------------

def build_vectorstore() -> None:
    """
    Creates the FAISS vector store from all markdown files in data/.

    We keep it in memory for now because:
    - it is simpler for Week 2 / project deliverable
    - it avoids extra persistence complexity
    - it clearly satisfies the requirement to load + index data
    """
    global VECTORSTORE

    docs = load_all_documents()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120
    )

    chunks = []
    metadatas = []

    for filename, content in docs:
        split_chunks = text_splitter.split_text(content)

        for i, chunk in enumerate(split_chunks):
            chunks.append(chunk)
            metadatas.append({
                "source_file": filename,
                "chunk_id": i
            })

    if not chunks:
        raise ValueError("No chunks created from data files.")

    # We keep embeddings creation inside build_vectorstore()
    # because it belongs to the vector index creation step.
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

    VECTORSTORE = FAISS.from_texts(
        texts=chunks,
        embedding=embeddings,
        metadatas=metadatas
    )


def ensure_vectorstore() -> None:
    """
    Lazy initialization:
    build vector store only once, at first query.
    """
    global VECTORSTORE

    if VECTORSTORE is None:
        build_vectorstore()


# -------------------------------------------------
# STEP 3 — SENSITIVE MATTERS REDIRECT
# -------------------------------------------------

def is_sensitive_wellbeing_question(text: str) -> bool:
    """
    If question is about harassment / bullying / whistleblowing,
    the bot must NOT answer from bot logic.
    It must redirect to the ombudsman.
    """
    lowered = text.lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


# -------------------------------------------------
# STEP 4 — RETRIEVE RELEVANT CONTEXT
# -------------------------------------------------

def retrieve_context(query: str, k: int = 3) -> Tuple[str, str]:
    """
    Retrieves the most relevant chunks from the vector store.

    Returns:
        context_text: combined retrieved chunks
        source_text: readable source summary
    """
    ensure_vectorstore()

    docs = VECTORSTORE.similarity_search(query, k=k)

    if not docs:
        raise ValueError("No relevant information found in the indexed data.")

    context_parts = []
    source_parts = []

    for doc in docs:
        context_parts.append(doc.page_content)
        source_file = doc.metadata.get("source_file", "unknown_file")
        chunk_id = doc.metadata.get("chunk_id", "?")
        source_parts.append(f"{source_file} (chunk {chunk_id})")

    context_text = "\n\n---\n\n".join(context_parts)
    source_text = "; ".join(source_parts)

    return context_text, source_text


# -------------------------------------------------
# STEP 5 — STRICT ANSWERING FROM PROVIDED TEXT ONLY
# -------------------------------------------------

def generate_strict_answer(question: str, context: str) -> str:
    """
    Gemini is used only as a constrained answer writer.
    It must use ONLY retrieved internal context.
    It must not guess.
    It must redirect sensitive matters.
    """
    prompt = f"""
You are the GreenLeaf internal HR assistant.

STRICT RULES:
1. Use ONLY the provided CONTEXT below.
2. Do NOT use outside knowledge.
3. Do NOT guess or invent missing information.
4. If the answer is not clearly in the context, say:
   "I could not find this information in the provided GreenLeaf documents."
5. If the question is about harassment, bullying, whistleblowing, or serious misconduct,
   do NOT answer the substance. Instead say:
   "For peers disputes or conflicts, employees should first attempt a 'Coffee Chat' to resolve the issue. If the matter involves serious misconduct, harassment, bullying, or whistleblowing, please contact the confidential ombudsman at ombudsman@greenleaf-safety.ch."
6. Keep the answer clear and professional.

QUESTION:
{question}

CONTEXT:
{context}
"""
    response = model.generate_content(prompt)
    return response.text.strip()


# -------------------------------------------------
# PUBLIC FUNCTION — called by brain.py
# -------------------------------------------------

def query_handbook(text: str) -> dict:
    """
    Interface contract (same shape expected by brain.py):
        Input:  text: str
        Output: {"answer": str, "source": str} or {"error": str}

    This function covers:
    - Office Etiquette
    - Kitchen rules
    - Conflict Resolution
    - Other internal handbook/data questions found in data/
    """
    try:
        # First: redirect sensitive matters exactly as required
        if is_sensitive_wellbeing_question(text):
            return {
                "answer": (
                    "For harassment, bullying, whistleblowing, or serious misconduct, "
                    f"please contact the confidential ombudsman at {OMBUDSMAN_EMAIL}."
                ),
                "source": "GreenLeaf Handbook — Section 9: Sensitive Matters & Conduct"
            }

        # Retrieve relevant internal context
        context, source = retrieve_context(text, k=3)

        # Generate strict answer only from provided text
        answer = generate_strict_answer(text, context)

        return {
            "answer": answer,
            "source": f"GreenLeaf internal documents — {source}"
        }

    except Exception as e:
        return {
            "error": f"policy_wellbeing query failed: {str(e)}"
        }


# -------------------------------------------------
# OPTIONAL LOCAL TEST ENTRY
# -------------------------------------------------

if __name__ == "__main__":
    print("Testing policy_wellbeing.py ...")
    try:
        build_vectorstore()
        print("✅ Vector store built successfully from data/ folder.")
        test_question = "What happens to food in the fridge on Friday?"
        result = query_handbook(test_question)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")
# >>> HOOMAN END