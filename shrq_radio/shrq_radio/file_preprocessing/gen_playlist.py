import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests

# --------------------
# CONFIG
# --------------------

OLLAMA_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.2:1b"


# --------------------
# OLLAMA HELPERS
# --------------------

def ollama_chat(prompt: str, model: str = CHAT_MODEL) -> str:
    """Call /api/chat, fall back to /api/generate if needed."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You translate natural-language music playlist requests into JSON filter criteria. "
                        "You MUST respond with a JSON object only, no backticks, no explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=120,
    )

    if resp.status_code in (404, 405):
        # Older Ollama: fall back to /api/generate
        return ollama_generate(prompt, model)

    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"].strip()


def ollama_generate(prompt: str, model: str = CHAT_MODEL) -> str:
    """Fallback to /api/generate."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "").strip()


# --------------------
# JSON UTILS
# --------------------

def extract_json_block(text: str) -> str:
    """Extract first {...} JSON object from a string."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return text[start: end + 1]


def infer_year_range_from_request(user_request: str) -> Tuple[Optional[int], Optional[int]]:
    text = user_request.lower()

    # e.g. "1970s", "1980s", etc.
    for decade_start in (1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020):
        token = f"{decade_start}s"
        if token in text:
            return decade_start, decade_start + 9

    # short forms like "80s"
    short = {
        "50s": 1950, "60s": 1960, "70s": 1970, "80s": 1980, "90s": 1990,
        "00s": 2000, "0s": 2000, "10s": 2010, "20s": 2020,
    }
    for token, start in short.items():
        if token in text:
            return start, start + 9

    return None, None


# --------------------
# BUILD FILTER CRITERIA WITH LLM
# --------------------

def build_filter_criteria_with_llm(user_request: str, sample_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ask Ollama to turn the user's request into structured filter criteria.
    """
    prompt = f"""
You help filter a music library.

Each song is a JSON object with (at least) these keys:
- "title": string
- "artist": string
- "album": string
- "genre": string or null
- "date": a string year like "2012" (sometimes empty)
- "bpm": number or null
- "loudness": number or null
- "energy": string like "123_-14.2" or empty

Here is a SAMPLE of the library (only to understand structure, not to filter):

{json.dumps(sample_rows, indent=2)}

USER REQUEST:
\"\"\"{user_request}\"\"\"\

Your task:
Return ONLY a JSON object with this exact schema:

{{
  "must_contain": {{
    "title": [],
    "artist": [],
    "album": [],
    "genre": []
  }},
  "year_min": null,
  "year_max": null,
  "bpm_min": null,
  "bpm_max": null,
  "exclude_genres": []
}}

Rules:
- all values lowercase
- no stopwords
- no empty strings
- never exclude genres user actually wants
- no backticks, no explanation, only JSON
"""

    raw = ollama_chat(prompt)
    json_str = extract_json_block(raw)
    return json.loads(json_str)


def normalize_criteria(raw: dict, user_request: str) -> dict:
    """
    Clean up + coerce LLM output into a robust criteria dict.
    """
    crit: Dict[str, Any] = {}

    # Helper converters
    def to_int(x):
        return int(x) if isinstance(x, (int, float)) else None

    def to_float(x):
        return float(x) if isinstance(x, (int, float)) else None

    crit["year_min"] = to_int(raw.get("year_min"))
    crit["year_max"] = to_int(raw.get("year_max"))
    crit["bpm_min"] = to_float(raw.get("bpm_min"))
    crit["bpm_max"] = to_float(raw.get("bpm_max"))

    # Infer decade from prompt if missing / too broad
    dmin, dmax = infer_year_range_from_request(user_request)
    if dmin is not None and dmax is not None:
        if crit["year_min"] is None or crit["year_min"] < dmin:
            crit["year_min"] = dmin
        if crit["year_max"] is None or crit["year_max"] > dmax:
            crit["year_max"] = dmax

    # Excluded genres
    excl = raw.get("exclude_genres", [])
    if not isinstance(excl, list):
        excl = []
    crit["exclude_genres"] = [str(g).lower() for g in excl if str(g).strip()]

    # Must-contain tokens
    STOP = {"", "the", "of", "and", "a", "to", "in", "on", "at", "by", "with"}

    must_raw = raw.get("must_contain", {})
    if not isinstance(must_raw, dict):
        must_raw = {}

    must: Dict[str, List[str]] = {}

    for field in ["title", "artist", "album", "genre"]:
        vals = []

        # Primary field in must_contain
        field_vals = must_raw.get(field)
        if isinstance(field_vals, list):
            vals.extend(field_vals)

        # Backwards-compat: some earlier prompts put arrays at top level (e.g. "artist": [...])
        top_vals = raw.get(field)
        if isinstance(top_vals, list):
            vals.extend(top_vals)

        cleaned = []
        for v in vals:
            v = str(v).strip().lower()
            if v and v not in STOP:
                cleaned.append(v)

        must[field] = cleaned

    crit["must_contain"] = must

    return crit


# --------------------
# LIBRARY HELPERS
# --------------------

def parse_year(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    date_str = str(date_str)

    # Look for a 4-digit year anywhere
    for part in date_str.replace("/", "-").split("-"):
        if part.isdigit() and len(part) == 4:
            return int(part)

    if date_str.isdigit() and len(date_str) == 4:
        return int(date_str)

    return None


def song_matches_criteria(song: Dict[str, Any], crit: Dict[str, Any]) -> bool:
    """Apply the filter criteria to a single song dict."""
    title = (song.get("title") or "").lower()
    artist = (song.get("artist") or "").lower()
    album = (song.get("album") or "").lower()
    genre = (song.get("genre") or "").lower()
    year = parse_year(song.get("date") or "")
    bpm = song.get("bpm")

    # 1) must_contain tokens
    must = crit.get("must_contain", {})
    for field, subs in must.items():
        val = {
            "title": title,
            "artist": artist,
            "album": album,
            "genre": genre,
        }.get(field, "")

        for s in subs:
            if s not in val:
                return False

    # 2) Year range
    ymin = crit.get("year_min")
    ymax = crit.get("year_max")
    if ymin is not None or ymax is not None:
        if year is None:
            return False
        if ymin is not None and year < ymin:
            return False
        if ymax is not None and year > ymax:
            return False

    # 3) BPM range
    bmin = crit.get("bpm_min")
    bmax = crit.get("bpm_max")
    if bmin is not None or bmax is not None:
        if bpm is None:
            return False
        try:
            b = float(bpm)
        except Exception:
            return False
        if bmin is not None and b < bmin:
            return False
        if bmax is not None and b > bmax:
            return False

    # 4) Excluded genres
    excl = crit.get("exclude_genres", [])
    for g in excl:
        if g in genre:
            return False

    return True


def load_library(db_path: Path) -> List[Dict[str, Any]]:
    """
    Load your mp3_rag_db.json and turn each document into a flat "song" dict.
    Now includes 'energy' pulled from tags.
    """
    db = json.loads(db_path.read_text(encoding="utf-8"))
    docs = db.get("documents", [])

    library: List[Dict[str, Any]] = []
    for d in docs:
        tags = d.get("tags", {})

        song = {
            "title": tags.get("title", ""),
            "artist": tags.get("artist", ""),
            "album": tags.get("album", ""),
            "genre": tags.get("genre", ""),
            "date": tags.get("date", tags.get("originaldate", "")),
            "bpm": d.get("bpm"),
            "loudness": d.get("loudness"),
            "energy": tags.get("energy", ""),   # <-- ENERGY ADDED HERE
            "path": d.get("path"),
        }
        library.append(song)

    return library


# --------------------
# CLI
# --------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a playlist from mp3_rag_db.json using Ollama as a filter-planner."
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Natural language playlist request, e.g. 'indie rock from the 2010s around 120 BPM'",
    )
    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Path to mp3_rag_db.json",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=30,
        help="Maximum number of tracks in the playlist",
    )
    args = parser.parse_args()

    user_request = " ".join(args.query).strip()
    if not user_request:
        user_request = input("Describe the playlist you want: ").strip()

    db_path = Path(args.db).expanduser()
    library = load_library(db_path)

    # Small sample to show Ollama the structure
    sample_rows = library[:20]

    print("\nAsking LLM to generate filter criteria...\n")
    raw_criteria = build_filter_criteria_with_llm(user_request, sample_rows)

    print("[Raw criteria from LLM]")
    print(json.dumps(raw_criteria, indent=2))

    criteria = normalize_criteria(raw_criteria, user_request)

    print("\n[Normalized criteria]")
    print(json.dumps(criteria, indent=2))

    print("\nFiltering full library...")

    playlist: List[Dict[str, Any]] = []
    for song in library:
        if song_matches_criteria(song, criteria):
            playlist.append(song)
            if len(playlist) >= args.k:
                break

    # ---- OUTPUT ----
    print(f"\n=== PLAYLIST ({len(playlist)} songs) ===\n")
    for song in playlist:
        print("──────────────")
        print(f"Filepath:  {song.get('path', '')}")
        print(f"Title:     {song.get('title', '')}")
        print(f"Artist:    {song.get('artist', '')}")
        print(f"Genre:     {song.get('genre', '')}")
        print(f"Year:      {song.get('date', '')}")
        print(f"BPM:       {song.get('bpm', '')}")
        print(f"Energy:    {song.get('energy', '')}")   # <-- ENERGY PRINTED HERE
        print(f"Loudness:  {song.get('loudness', '')}")
    print("──────────────\n")


if __name__ == "__main__":
    main()
