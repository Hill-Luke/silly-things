import argparse
import json
import math
import os
import re
from pathlib import Path

import requests
from mutagen.easyid3 import EasyID3
from tqdm import tqdm

OLLAMA_URL = "http://localhost:11434"

# Model used when BUILDING the DB (for embeddings).
# The actual model name will be stored in the DB as db["model"].
LLM_MODEL = "llama3.2:1b"

# Basic stopwords so lexical filter doesn't match every doc on generic words
STOPWORDS = {
    "what", "album", "song", "songs", "year", "from", "the", "and", "with",
    "this", "that", "track", "tracks", "is", "by", "for", "about", "show",
    "me", "high", "energy", "high-energy"
}


# ---------------------- Embeddings & Generation ---------------------- #

def get_embedding(text: str, model: str = LLM_MODEL):
    """Get an embedding vector from Ollama for a given text."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embedding"]   # list[float]


def generate_with_context(query: str, docs, model: str) -> str:
    """
    Call Ollama's /api/generate endpoint with RAG context.

    `docs` is a list of document dicts from the DB.
    """
    context_chunks = [d["text"] for d in docs]
    context_text = "\n\n".join(context_chunks)

    system_prompt = (
        "You are an assistant that helps the user explore a music library.\n"
        "You are given context about MP3 tags (title, artist, album, genre, BPM, loudness, etc.).\n"
        "Answer the user's question using ONLY this context. If something isn't "
        "in the context, say you don't see it."
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"Context about MP3 files:\n{context_text}\n\n"
        f"Question: {query}"
    )

    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False,
    }

    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # /api/generate returns {"response": "...", ...}
    return data.get("response", "")


# ---------------------- Tag Extraction ---------------------- #

def read_mp3_tags(path: Path) -> dict:
    """Return a dict of 'nice' tags for an MP3 file."""
    try:
        audio = EasyID3(str(path))
    except Exception:
        return {}

    tags = {}
    for key, val in audio.items():
        # val is usually a list of strings
        tags[key] = ", ".join(val)
    return tags


def parse_energy_value(energy_val: str):
    """
    Parse energy tag of the form '{BPM}_{Loudness}' into (bpm, loudness).

    Examples:
        '123_-14.2' -> (123.0, -14.2)
        '98_-9'     -> (98.0, -9.0)

    Returns (None, None) if parsing fails.
    """
    if not energy_val:
        return None, None

    try:
        bpm_str, loud_str = energy_val.split("_", 1)
        bpm = float(bpm_str)
        loudness = float(loud_str)
        return bpm, loudness
    except Exception:
        return None, None


def build_doc_from_tags(path: Path, tags: dict) -> tuple[str, float | None, float | None]:
    """
    Convert tags into a single text blob for embedding and also return
    numeric bpm and loudness (if parsed from energy).
    """
    title = tags.get("title", "")
    artist = tags.get("artist", "")
    album = tags.get("album", "")
    genre = tags.get("genre", "")
    date = tags.get("date", tags.get("originaldate", ""))

    # Energy tag: expected '{BPM}_{Loudness}'
    energy = tags.get("energy", "")  # assumes you've registered EasyID3 key 'energy'
    bpm_val, loudness_val = parse_energy_value(energy)

    # This is what RAG will actually see
    lines = [
        f"Path: {path}",
        f"Title: {title}",
        f"Artist: {artist}",
        f"Album: {album}",
        f"Genre: {genre}",
        f"Date: {date}",
        f"Energy: {energy}",
        f"BPM: {bpm_val if bpm_val is not None else ''}",
        f"Loudness: {loudness_val if loudness_val is not None else ''}",
    ]

    # Dump remaining tags too (including any other custom fields)
    extras = {
        k: v
        for k, v in tags.items()
        if k not in {
            "title",
            "artist",
            "album",
            "genre",
            "date",
            "originaldate",
            "energy",
        }
    }
    if extras:
        lines.append("Other tags:")
        for k, v in extras.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines), bpm_val, loudness_val


# ---------------------- Vector Search ---------------------- #

def cosine_similarity(a, b) -> float:
    """Compute cosine similarity between two float lists."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / norm_a / norm_b


def lexical_prefilter(docs, query: str):
    """
    Lexical filter to narrow down candidates *before* doing embedding similarity.

    - Tokenize the query.
    - Drop short tokens and stopwords.
    - Keep docs whose text contains any of the remaining tokens (case-insensitive).
    - Fallback to ALL docs if nothing matches.
    """
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9']+", query)
        if len(t) > 2 and t.lower() not in STOPWORDS
    ]

    if not tokens:
        return docs

    filtered = []
    for d in docs:
        text = d.get("text", "").lower()
        if any(tok in text for tok in tokens):
            filtered.append(d)

    return filtered or docs


# ---------------------- Build / Query RAG DB ---------------------- #

def build_db(music_dir: Path, db_path: Path):
    """Scan folder, read tags, get embeddings, and write JSON DB."""
    files = sorted(music_dir.rglob("*.mp3"))
    if not files:
        print("No MP3 files found.")
        return

    docs = []
    print(f"Indexing {len(files)} MP3 files...")

    for idx, mp3_path in enumerate(tqdm(files, desc="Building RAG DB")):
        tags = read_mp3_tags(mp3_path)
        if not tags:
            continue

        text, bpm_val, loudness_val = build_doc_from_tags(mp3_path, tags)
        try:
            # Use LLM_MODEL for embeddings when building;
            # this model name will be saved into the DB.
            embedding = get_embedding(text, model=LLM_MODEL)
        except Exception as e:
            print(f"Failed to embed {mp3_path}: {e}")
            continue

        docs.append(
            {
                "id": idx,
                "path": str(mp3_path),
                "tags": tags,          # original tags
                "bpm": bpm_val,        # parsed from energy (or None)
                "loudness": loudness_val,
                "text": text,
                "embedding": embedding,
            }
        )

    db = {
        # Store the embedding model used so queries can re-use it.
        "model": LLM_MODEL,
        "documents": docs,
    }

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("w", encoding="utf-8") as f:
        json.dump(db, f)

    print(f"Saved RAG DB with {len(docs)} documents to {db_path}")


def query_db(db_path: Path, query: str, top_k: int = 5, chat_model: str | None = None):
    """Load DB, embed query, retrieve top_k docs, and ask LLM."""
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return

    with db_path.open("r", encoding="utf-8") as f:
        db = json.load(f)

    docs = db.get("documents", [])
    if not docs:
        print("No documents in DB.")
        return

    # Embedding model used when building the DB
    emb_model = db.get("model", LLM_MODEL)

    # By default, answer with the same model; can be overridden if desired.
    if chat_model is None:
        chat_model = emb_model

    # Lexical prefilter to narrow candidate docs
    candidates = lexical_prefilter(docs, query)

    # Embed the query using the SAME model as stored in the DB
    query_emb = get_embedding(query, model=emb_model)

    # Rank candidate documents
    scored = []
    for doc in candidates:
        sim = cosine_similarity(query_emb, doc["embedding"])
        scored.append((sim, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_docs = [doc for sim, doc in scored[:top_k]]

    # Ask LLM with RAG context
    answer = generate_with_context(query, top_docs, model=chat_model)

    print("\n=== Answer ===\n")
    print(answer)

    print("\n=== Top matches ===\n")
    for sim, doc in scored[:top_k]:
        print(
            f"{sim:.3f} :: {doc['path']}  "
            f"(BPM={doc.get('bpm')}, Loudness={doc.get('loudness')})"
        )


# ---------------------- CLI ---------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Simple RAG over MP3 tags using Ollama + llama3.2:1b"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = subparsers.add_parser("build", help="Build RAG DB from a music folder")
    p_build.add_argument("music_dir", type=str, help="Folder containing MP3 files")
    p_build.add_argument(
        "--db",
        type=str,
        default="mp3_rag_db.json",
        help="Output path for RAG DB JSON",
    )

    # query
    p_query = subparsers.add_parser("query", help="Query the RAG DB")
    p_query.add_argument("--db", type=str, default="mp3_rag_db.json", help="DB path")
    p_query.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model to use for answering (default: same as DB embedding model)",
    )
    p_query.add_argument("question", type=str, help="Natural language question")

    args = parser.parse_args()

    if args.command == "build":
        music_dir = Path(args.music_dir).expanduser()
        db_path = Path(args.db).expanduser()
        build_db(music_dir, db_path)
    elif args.command == "query":
        db_path = Path(args.db).expanduser()
        query_db(db_path, args.question, chat_model=args.model)


if __name__ == "__main__":
    main()

# Example usage:
# 1) Build the DB from your music folder
# python mp3_rag.py build "C:/path/to/music" --db mp3_rag_db.json
#
# 2) Ask questions about your library
# python mp3_rag.py query --db mp3_rag_db.json "Show me high-energy rock tracks from the 1970s"
