"""
Knowledge Base Loader — fetches articles from Google Sheets and indexes them
into ChromaDB for semantic search.
"""

import hashlib
import httpx
import json
import re
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from config import GOOGLE_SHEET_ID, KB_SHEET_NAME, CHROMA_PERSIST_DIR


def get_embeddings():
    """Get HuggingFace embeddings model (runs locally, free)."""
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def fetch_kb_from_sheets() -> list[dict]:
    """Fetch knowledge base articles from Google Sheets via public gviz endpoint."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
        f"/gviz/tq?tqx=out:json&sheet={KB_SHEET_NAME}"
    )

    response = httpx.get(url, timeout=15.0)
    response.raise_for_status()

    # Parse gviz response (wrapped in callback)
    text = response.text
    start = text.index("{")
    end = text.rindex("}") + 1
    data = json.loads(text[start:end])

    table = data.get("table", {})
    cols = table.get("cols", [])
    rows = table.get("rows", [])

    if not cols or not rows:
        return []

    headers = [c.get("label", c.get("id", "")).strip() for c in cols]

    articles = []
    for row in rows:
        if not row or not row.get("c"):
            continue
        cells = row["c"]
        obj = {}
        for i, header in enumerate(headers):
            cell = cells[i] if i < len(cells) else None
            obj[header] = str(cell["v"]).strip() if cell and cell.get("v") is not None else ""

        if obj.get("title") and obj.get("fullText"):
            articles.append(obj)

    return articles


def load_local_kb() -> list[dict]:
    """Load KB from local markdown files as fallback."""
    kb_dir = Path(__file__).parent / "knowledge_base"
    if not kb_dir.exists():
        return []

    articles = []
    for md_file in kb_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        title = md_file.stem.replace("-", " ").replace("_", " ").title()
        articles.append({
            "articleId": hashlib.md5(md_file.name.encode()).hexdigest()[:12],
            "title": title,
            "source": "local",
            "category": "general",
            "summary": content[:200],
            "fullText": content,
            "url": "",
        })

    return articles


def build_vector_store(force_rebuild: bool = False) -> Chroma:
    """Build or load the ChromaDB vector store with KB articles."""
    embeddings = get_embeddings()
    persist_dir = CHROMA_PERSIST_DIR

    # Check if store already exists
    if not force_rebuild and Path(persist_dir).exists():
        try:
            store = Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
                collection_name="pet_care_kb",
            )
            # Verify it has documents
            if store._collection.count() > 0:
                return store
        except Exception:
            pass

    # Fetch articles
    articles = fetch_kb_from_sheets()
    if not articles:
        articles = load_local_kb()

    if not articles:
        # Create empty store
        return Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings,
            collection_name="pet_care_kb",
        )

    # Split long articles into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " "],
    )

    texts = []
    metadatas = []
    for article in articles:
        chunks = splitter.split_text(article["fullText"])
        for i, chunk in enumerate(chunks):
            texts.append(chunk)
            metadatas.append({
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "category": article.get("category", ""),
                "url": article.get("url", ""),
                "article_id": article.get("articleId", ""),
                "chunk_index": i,
            })

    # Create vector store
    store = Chroma.from_texts(
        texts=texts,
        metadatas=metadatas,
        embedding=embeddings,
        persist_directory=persist_dir,
        collection_name="pet_care_kb",
    )

    return store


if __name__ == "__main__":
    print("Building vector store from knowledge base...")
    store = build_vector_store(force_rebuild=True)
    count = store._collection.count()
    print(f"Done! Indexed {count} chunks into ChromaDB at {CHROMA_PERSIST_DIR}")
