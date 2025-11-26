import argparse
import json
import math
from pathlib import Path
from typing import List, Dict, Any
import requests

# =========================
# CONFIG
# =========================

DEFAULT_DB_PATH = Path(
    r"C:\\Users\\lukeh\\Documents\\repos\\silly-things\\shrq_radio\\shrq_radio\\file_preprocessing\\mp3_rag_db.json"
)

OLLAMA_URL = "http://localhost:11434"


# =========================
# DB / EMBEDDINGS
# =========================

def load_db(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        db = json.load(f)

    embed_model = db.get("embed_model") or db.get("model")
    if embed_model is None:
        raise ValueError("DB missing 'embed_model' or 'model'")

    db["_resolved_embed_model"] = embed_model
    return db


def embed_text(text: str, model: str) -> List[float]:
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# =========================
# RETRIEVER
# =========================

def retrieve_top_k(db: Dict[str, Any], question: str, k: int):
    embed_model = db["_resolved_embed_model"]
    docs = db["documents"]

    q_emb = embed_text(question, embed_model)

    scored = []
    for d in docs:
        emb = d.get("embedding")
        if not emb:
            continue
        sim = cosine_similarity(q_emb, emb)
        scored.append((sim, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]


def tag(d: Dict[str, Any], key: str) -> str:
    tags = d.get("tags") or {}
    val = tags.get(key, "")
    return val if isinstance(val, str) else str(val)


# =========================
# CLI
# =========================

def main():
    parser = argparse.ArgumentParser(description="Retrieve top matching MP3 tracks.")
    parser.add_argument("question", nargs="*", help="Query about your music library.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to DB JSON")
    parser.add_argument("-k", type=int, default=20, help="Number of results to show")
    args = parser.parse_args()

    question = " ".join(args.question).strip() if args.question else input("Query: ")

    db = load_db(Path(args.db))
    top_docs = retrieve_top_k(db, question, args.k)

    print(f"\n=== TOP {args.k} MATCHES ===\n")

    for d in top_docs:
        title = tag(d, "title") or "<no title>"
        artist = tag(d, "artist") or "<no artist>"
        album = tag(d, "album") or "<no album>"
        path = d.get("path", "")
        print(f"- {title} — {artist}  [{album}]\n  {path}\n")

    print("===========================\n")


if __name__ == "__main__":
    main()
