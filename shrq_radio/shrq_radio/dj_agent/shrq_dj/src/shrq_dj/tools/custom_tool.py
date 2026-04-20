from typing import Type, List, Dict, Any, Optional, Tuple

import json
import os
import random
import re
import sys
from collections import Counter

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# -------------------------
# Shared helpers
# -------------------------

KEY_ALIASES = {
    "TIT2": "Trackname",
    "title": "Trackname",
    "track": "Trackname",
    "trackname": "Trackname",
    "name": "Trackname",
    "TPE1": "Artist",
    "artist": "Artist",
    "TALB": "Album",
    "album": "Album",
    "TDRC": "Year",
    "year": "Year",
    "date": "Year",
    "TCON": "Genre",
    "genre": "Genre",
    "style": "Genre",
    "TXXX:energy": "energy",
    "energy": "energy",
    "bpm": "bpm",
    "tempo": "bpm",
    "filepath": "Filepath",
    "file_path": "Filepath",
    "path": "Filepath",
    "filename": "Filepath",
    "full_path": "Filepath",
}

KNOWN_GENRES = [
    "pop", "rock", "hip hop", "rap", "r&b", "jazz", "blues", "country", "folk",
    "electronic", "edm", "house", "techno", "drum and bass", "indie", "metal",
    "punk", "classical", "latin", "reggaeton", "soul", "funk", "disco", "lofi",
]

ENERGY_MIN = 1
ENERGY_MAX = 100


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return fallback
        # Tolerate fenced JSON occasionally emitted by LLMs.
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return fallback
    return fallback


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, val in record.items():
        key_str = str(key)
        canonical = KEY_ALIASES.get(key_str, KEY_ALIASES.get(key_str.lower(), key_str))
        normalized[canonical] = val
    return normalized


def _normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_normalize_record(r) for r in records]


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _word_to_int(text: str) -> Optional[int]:
    # Simple mapping for common number words used in queries.
    if not isinstance(text, str):
        return None
    t = text.strip().lower()
    small = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
    }
    # Direct match
    if t in small:
        return small[t]

    # Composite like 'twenty five' or 'ninety two'
    parts = re.findall(r"[a-z]+", t)
    if parts:
        total = 0
        last = 0
        for p in parts:
            v = small.get(p)
            if v is None:
                continue
            if v == 100:
                if last == 0:
                    last = 1
                last = last * v
                total += last
                last = 0
            else:
                last += v
        total += last
        if total > 0:
            return total

    # Extract digits if present (e.g., '10', '10 tracks')
    m = re.search(r"(\d{1,4})", t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> Optional[int]:
    # Try robust coercion for ints: numeric strings, floats, and common words.
    if isinstance(value, int):
        return value
    if value is None:
        return None
    # Try direct numeric parsing
    n = _to_int(value)
    if n is not None:
        return n
    # Try word parsing
    if isinstance(value, str):
        w = _word_to_int(value)
        if w is not None:
            return w
    return None


def _extract_year_range(query: str) -> Tuple[Optional[int], Optional[int]]:
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", query)]
    if len(years) >= 2:
        return min(years), max(years)
    if len(years) == 1:
        return years[0], years[0]

    decade_match = re.search(r"\b(\d{2})s\b", query)
    if decade_match:
        yy = int(decade_match.group(1))
        century = 2000 if yy <= 30 else 1900
        start = century + yy
        return start, start + 9

    return None, None


def _extract_track_count(query: str) -> Optional[int]:
    match = re.search(r"\b(\d{1,3})\s*(tracks?|songs?)\b", query)
    if match:
        return int(match.group(1))
    return None


def _clamp_energy(value: int) -> int:
    return max(ENERGY_MIN, min(ENERGY_MAX, int(value)))


def _extract_energy_range(query: str) -> Tuple[Optional[int], Optional[int]]:
    q = query.lower()

    # Numeric forms: "energy between 30 and 60", "30-60 energy"
    range_match = re.search(
        r"\benergy(?:\s+level)?\s*(?:between\s*)?(\d{1,3})\s*(?:-|–|—|to|and)\s*(\d{1,3})\b",
        q,
    )
    if not range_match:
        range_match = re.search(
            r"\b(\d{1,3})\s*(?:-|–|—|to)\s*(\d{1,3})\s*(?:energy|energy level)\b",
            q,
        )
    if range_match:
        a = _clamp_energy(int(range_match.group(1)))
        b = _clamp_energy(int(range_match.group(2)))
        return min(a, b), max(a, b)

    min_match = re.search(
        r"\b(?:energy(?:\s+level)?\s*)?(?:above|over|min(?:imum)?|at least)\s*(\d{1,3})\s*(?:energy)?\b",
        q,
    )
    max_match = re.search(
        r"\b(?:energy(?:\s+level)?\s*)?(?:below|under|max(?:imum)?|at most)\s*(\d{1,3})\s*(?:energy)?\b",
        q,
    )
    if min_match or max_match:
        e_min = _clamp_energy(int(min_match.group(1))) if min_match else None
        e_max = _clamp_energy(int(max_match.group(1))) if max_match else None
        return e_min, e_max

    if any(word in q for word in ["very low energy", "super chill", "sleep"]):
        return 1, 30
    if any(word in q for word in ["chill", "calm", "ambient", "soft", "relax"]):
        return 20, 45
    if any(word in q for word in ["mid energy", "moderate", "balanced"]):
        return 40, 65
    if any(word in q for word in ["high energy", "energetic", "hype", "workout", "intense"]):
        return 65, 100
    return None, None


def _normalize_energy_value(value: Any) -> Optional[int]:
    if value is None:
        return None

    as_float = _to_float(value)
    if as_float is not None:
        # Backward compatibility for old normalized energy values in [0, 1].
        if 0.0 <= as_float <= 1.0:
            return _clamp_energy(int(round((as_float * 99.0) + 1.0)))
        as_int = _to_int(as_float)
        if as_int is not None:
            return _clamp_energy(as_int)

    as_int = _coerce_int(value)
    if as_int is not None:
        return _clamp_energy(as_int)

    label = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    # Legacy categorical tags mapped to representative numeric values.
    aliases = {
        "low_low": 8,
        "lowlow": 8,
        "low": 12,
        "medium_low": 22,
        "med_low": 22,
        "mediumlow": 22,
        "high_low": 35,
        "highlow": 35,
        "medium_medium": 50,
        "mediummedium": 50,
        "med": 50,
        "medium": 50,
        "mid": 50,
        "medium_high": 64,
        "med_high": 64,
        "mediumhigh": 64,
        "high_medium": 78,
        "highmedium": 78,
        "high_high": 92,
        "highhigh": 92,
        "high": 88,
        "vlow": 6,
        "vhigh": 96,
        "very_low": 6,
        "very_high": 96,
    }
    return aliases.get(label)


def _energy_bucket(value: Any) -> Optional[str]:
    score = _normalize_energy_value(value)
    if score is None:
        return None
    if score <= 20:
        return "1-20"
    if score <= 40:
        return "21-40"
    if score <= 60:
        return "41-60"
    if score <= 80:
        return "61-80"
    return "81-100"


def _extract_bpm_range(query: str) -> Tuple[Optional[float], Optional[float]]:
    q = query.lower()
    # Accept forms like '100-120 bpm', '100 to 120 bpm', 'between 100 and 120 bpm'
    range_match = re.search(r"\b(\d{2,3})\s*(?:-|–|—|to)\s*(\d{2,3})\s*bpm\b", q)
    if not range_match:
        range_match = re.search(r"\bbetween\s*(\d{2,3})\s*(?:and|to|-)\s*(\d{2,3})\s*bpm\b", q)
    if range_match:
        a = float(range_match.group(1))
        b = float(range_match.group(2))
        return min(a, b), max(a, b)

    min_match = re.search(r"\b(?:above|over|min(?:imum)?|at least)\s*(\d{2,3})\s*bpm\b", q)
    max_match = re.search(r"\b(?:below|under|max(?:imum)?|at most)\s*(\d{2,3})\s*bpm\b", q)
    if min_match or max_match:
        return float(min_match.group(1)) if min_match else None, float(max_match.group(1)) if max_match else None

    if any(word in q for word in ["slow", "downtempo"]):
        return 60.0, 100.0
    if any(word in q for word in ["upbeat", "fast", "dance"]):
        return 110.0, 160.0

    return None, None


def _extract_genres(query: str) -> List[str]:
    q = query.lower()
    found = [g for g in KNOWN_GENRES if g in q]
    return list(dict.fromkeys(found))


def _parse_include_exclude(query: str) -> Tuple[List[str], List[str]]:
    q = query.lower()
    must_exclude: List[str] = []
    must_include: List[str] = []

    # Parse explicit exclusions.
    for pat in [
        r"(?:exclude|without|avoid|no)\s+([a-z0-9&\-\s]+)",
        r"not\s+(?:including|with)\s+([a-z0-9&\-\s]+)",
    ]:
        for m in re.findall(pat, q):
            token = m.strip().split(",")[0].strip()
            # Clean up common prefixes and quotes
            token = re.sub(r"^(the\s+)?band\s+", "", token, flags=re.IGNORECASE).strip("'\"").strip()
            if token:
                must_exclude.append(token)

    # Parse includes and artist/album hints.
    for pat in [
        r"include\s+([a-z0-9&\-\s]+)",
        r"must have\s+([a-z0-9&\-\s]+)",
        r"by\s+([a-z0-9&\-\s]+)",
        r"from\s+([a-z0-9&\-\s]+)",
    ]:
        for m in re.findall(pat, q):
            token = m.strip().split(",")[0].strip()
            if token:
                must_include.append(token)

    return list(dict.fromkeys(must_include)), list(dict.fromkeys(must_exclude))


def _constraint_tokens(value: str) -> List[str]:
    words = re.findall(r"[a-z0-9&\-]+", str(value).lower())
    stop = {
        "the", "and", "for", "with", "from", "into", "that", "this", "song",
        "songs", "track", "tracks", "artist", "album", "music",
    }
    return [w for w in words if len(w) >= 3 and w not in stop]


def _matches_include(text: str, includes: List[str]) -> bool:
    if not includes:
        return True

    for token in includes:
        token_l = str(token).strip().lower()
        if not token_l:
            continue
        if token_l in text:
            return True
        terms = _constraint_tokens(token_l)
        if terms and any(term in text for term in terms):
            return True

    return False


def _dedupe_by_track_artist(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in records:
        key = (str(r.get("Trackname", "")).lower(), str(r.get("Artist", "")).lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _record_text(record: Dict[str, Any]) -> str:
    return " ".join(
        str(record.get(k, ""))
        for k in ["Trackname", "Artist", "Album", "Genre", "Year", "Filepath"]
    ).lower()


def _load_records_from_path(db_path: str) -> List[Dict[str, Any]]:
    try:
        with open(db_path, "r") as f:
            payload = json.load(f)
    except FileNotFoundError as e:
        print(f"ERROR: Dataset file not found at {db_path}: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from {db_path}: {e}", file=sys.stderr)
        return []
    except OSError as e:
        print(f"ERROR: OS error reading {db_path}: {e}", file=sys.stderr)
        return []

    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


# -------------------------
# query_intake tool
# -------------------------

class QueryIntakeInput(BaseModel):
    query: str = Field("", description="Raw user query requesting playlist curation.")
    prompt: str = Field("", description="Alias for query.")
    user_query: str = Field("", description="Alias for query.")
    request: str = Field("", description="Alias for query.")


class QueryIntakeTool(BaseTool):
    name: str = "query_intake_tool"
    description: str = (
        "Turn a raw playlist query into structured JSON with clarified intent, "
        "playlist objectives, and constraints."
    )
    args_schema: Type[BaseModel] = QueryIntakeInput

    def _run(
        self,
        query: str = "",
        prompt: str = "",
        user_query: str = "",
        request: str = "",
    ) -> str:
        raw = query if query not in (None, "") else prompt
        if raw in (None, ""):
            raw = user_query
        if raw in (None, ""):
            raw = request

        parsed = _safe_json_loads(raw, fallback=raw)
        if isinstance(parsed, dict):
            raw = (
                parsed.get("query")
                or parsed.get("prompt")
                or parsed.get("user_query")
                or parsed.get("request")
                or ""
            )
        elif isinstance(parsed, list):
            raw = " ".join(str(x) for x in parsed if x is not None)
        else:
            raw = parsed

        q = str(raw).strip()
        if not q:
            q = "Build a coherent playlist matching user mood and intent."
        q_lower = q.lower()

        genres = _extract_genres(q_lower)
        y_min, y_max = _extract_year_range(q_lower)
        e_min, e_max = _extract_energy_range(q_lower)
        bpm_min, bpm_max = _extract_bpm_range(q_lower)
        target_count = _extract_track_count(q_lower)
        must_include, must_exclude = _parse_include_exclude(q_lower)

        objectives: List[str] = []
        if genres:
            objectives.append(f"Focus genres: {', '.join(genres)}")
        if y_min is not None or y_max is not None:
            objectives.append(f"Target era/year range: {y_min} to {y_max}")
        if e_min is not None or e_max is not None:
            objectives.append(f"Energy range: {e_min} to {e_max}")
        if bpm_min is not None or bpm_max is not None:
            objectives.append(f"Tempo BPM range: {bpm_min} to {bpm_max}")
        if target_count is not None:
            objectives.append(f"Target track count: {target_count}")
        if any(word in q_lower for word in ["morning", "night", "focus", "party", "workout", "study"]):
            objectives.append("Optimize for stated use case/time-of-day")
        if not objectives:
            objectives.append("Build a coherent playlist matching the user mood and intent")

        out = {
            "clarified_query": f"User wants a playlist that matches: {q}",
            "playlist_objectives": objectives,
            "constraints": {
                "genres": genres,
                "year_range": {"min": y_min, "max": y_max},
                "energy_range": {"min": e_min, "max": e_max},
                "tempo_bpm_range": {"min": bpm_min, "max": bpm_max},
                "target_track_count": target_count,
                "must_include": must_include,
                "must_exclude": must_exclude,
            },
        }
        return json.dumps(out)


# -------------------------
# select_relevant_fields tool
# -------------------------

class SelectRelevantFieldsInput(BaseModel):
    query_intake_json: str = Field(
        ..., description="JSON string output from query_intake task/tool."
    )
    records: str = Field(
        "",
        description="Optional dataset records as a JSON string.",
    )
    db: str = Field(
        "",
        description="Alias for records; accepts a JSON string.",
    )


class SelectRelevantFieldsTool(BaseTool):
    name: str = "select_relevant_fields_tool"
    description: str = (
        "Select minimal dataset fields needed to satisfy playlist objectives and constraints."
    )
    args_schema: Type[BaseModel] = SelectRelevantFieldsInput

    def _run(
        self,
        query_intake_json: str,
        records: str = "",
        db: str = "",
    ) -> str:
        source_records = _safe_json_loads(records, fallback=records)
        if not isinstance(source_records, list):
            source_records = _safe_json_loads(db, fallback=db)
        if isinstance(source_records, dict):
            source_records = [source_records]
        if not isinstance(source_records, list):
            source_records = []
        source_records = [r for r in source_records if isinstance(r, dict)]

        intake = _safe_json_loads(query_intake_json, fallback={})
        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}

        available = set()
        if source_records:
            norm = _normalize_records(source_records[:25])
            for rec in norm:
                available.update(rec.keys())

        # Always needed for identification/output
        selected = ["Trackname", "Artist", "Album"]
        rationale = {
            "Trackname": "Needed to identify each selected track.",
            "Artist": "Needed for attribution and diversity control.",
            "Album": "Useful metadata for playlist display/context.",
        }

        if constraints.get("genres"):
            selected.append("Genre")
            rationale["Genre"] = "Required to enforce requested genre constraints."

        year_range = constraints.get("year_range", {})
        if isinstance(year_range, dict) and (
            year_range.get("min") is not None or year_range.get("max") is not None
        ):
            selected.append("Year")
            rationale["Year"] = "Required to enforce year/era constraints."

        energy_range = constraints.get("energy_range", {})
        if isinstance(energy_range, dict) and (
            energy_range.get("min") is not None or energy_range.get("max") is not None
        ):
            selected.append("energy")
            rationale["energy"] = "Required to enforce requested energy bounds."

        bpm_range = constraints.get("tempo_bpm_range", {})
        if isinstance(bpm_range, dict) and (
            bpm_range.get("min") is not None or bpm_range.get("max") is not None
        ):
            selected.append("bpm")
            rationale["bpm"] = "Required to enforce tempo/BPM constraints."

        # If records were provided, keep only available + preserve order where possible
        if available:
            selected = [f for f in selected if f in available]
            if "Trackname" not in selected and "Trackname" in available:
                selected.insert(0, "Trackname")
            if "Artist" not in selected and "Artist" in available:
                selected.insert(1 if selected else 0, "Artist")

        out = {
            "selected_fields": list(dict.fromkeys(selected)),
            "field_rationale": {k: v for k, v in rationale.items() if k in selected},
            "ready_for_filtering": True,
        }
        return json.dumps(out)


# -------------------------
# filter_dataset tool
# -------------------------

class FilterDatasetInput(BaseModel):
    records: str = Field(
        "",
        description="Full dataset records as a JSON string.",
    )
    db: str = Field(
        "",
        description="Alias for records; accepts a JSON string.",
    )
    db_path: str = Field(
        "",
        description="Path to dataset JSON file. Used when records are not passed directly.",
    )
    query_intake_json: str = Field(..., description="JSON string output from query_intake.")
    selected_fields_json: str = Field(
        "",
        description="JSON string output from select_relevant_fields.",
    )
    limit: int = Field(
        120,
        description="Maximum number of candidate records to return.",
    )
    pre_sample_size: int = Field(
        400,
        description="Maximum size of random pre-sampled pool before final output limiting.",
    )


class FilterDatasetTool(BaseTool):
    name: str = "filter_dataset_tool"
    description: str = (
        "Filter dataset records using constraints derived from query intake and selected fields."
    )
    args_schema: Type[BaseModel] = FilterDatasetInput

    def _run(
        self,
        query_intake_json: str,
        records: str = "",
        db: str = "",
        db_path: str = "",
        selected_fields_json: str = "",
        limit: int = 120,
        pre_sample_size: int = 400,
    ) -> str:
        def _coerce_records(value: Any) -> List[Dict[str, Any]]:
            parsed = _safe_json_loads(value, fallback=value)
            if isinstance(parsed, dict):
                return [parsed]
            if isinstance(parsed, list):
                return [r for r in parsed if isinstance(r, dict)]
            return []

        records_source = _coerce_records(records) or _coerce_records(db)
        if not records_source:
            path = db_path or os.getenv("SHRQ_DB_PATH")
            if path:
                records_source = _load_records_from_path(path)

        intake = _safe_json_loads(query_intake_json, fallback={})
        selected_obj = _safe_json_loads(selected_fields_json, fallback={}) if selected_fields_json else {}

        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        selected_fields = selected_obj.get("selected_fields", []) if isinstance(selected_obj, dict) else []
        selected_fields = selected_fields if isinstance(selected_fields, list) else []
        target_count = _coerce_int(constraints.get("target_track_count"))

        genres = [str(g).lower() for g in constraints.get("genres", [])]
        year_range = constraints.get("year_range", {}) if isinstance(constraints.get("year_range", {}), dict) else {}
        energy_range = constraints.get("energy_range", {}) if isinstance(constraints.get("energy_range", {}), dict) else {}
        bpm_range = constraints.get("tempo_bpm_range", {}) if isinstance(constraints.get("tempo_bpm_range", {}), dict) else {}
        must_include = [str(x).lower() for x in constraints.get("must_include", [])]
        must_exclude = [str(x).lower() for x in constraints.get("must_exclude", [])]

        y_min = _to_int(year_range.get("min"))
        y_max = _to_int(year_range.get("max"))
        e_min = _normalize_energy_value(energy_range.get("min"))
        e_max = _normalize_energy_value(energy_range.get("max"))
        if e_min is not None and e_max is not None and e_min > e_max:
            e_min, e_max = e_max, e_min
        b_min = _to_float(bpm_range.get("min"))
        b_max = _to_float(bpm_range.get("max"))

        norm_records = _normalize_records(records_source)

        def _passes(
            rec: Dict[str, Any],
            use_genre: bool = True,
            use_year: bool = True,
            use_energy: bool = True,
            use_bpm: bool = True,
            use_include: bool = True,
            use_exclude: bool = True,
        ) -> bool:
            text = _record_text(rec)

            if use_genre and genres:
                rec_genre = str(rec.get("Genre", "")).lower()
                if not any(g in rec_genre for g in genres):
                    return False

            year_val = _to_int(rec.get("Year"))
            if use_year and y_min is not None and (year_val is None or year_val < y_min):
                return False
            if use_year and y_max is not None and (year_val is None or year_val > y_max):
                return False

            energy_val = _normalize_energy_value(rec.get("energy"))
            if use_energy and e_min is not None:
                if energy_val is None or energy_val < e_min:
                    return False
            if use_energy and e_max is not None:
                if energy_val is None or energy_val > e_max:
                    return False

            bpm_val = _to_float(rec.get("bpm"))
            if use_bpm and b_min is not None and (bpm_val is None or bpm_val < b_min):
                return False
            if use_bpm and b_max is not None and (bpm_val is None or bpm_val > b_max):
                return False

            if use_exclude and must_exclude and any(token in text for token in must_exclude):
                return False

            if use_include and must_include and not _matches_include(text, must_include):
                return False

            return True

        def _collect(**kwargs: Any) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for rec in norm_records:
                if _passes(rec, **kwargs):
                    out.append(rec)
                    if limit is not None and len(out) >= limit:
                        break
            return out

        filtered: List[Dict[str, Any]] = _collect()
        relaxation_note = "Strict filtering applied from parsed constraints."
        desired_pool = min(limit or 300, max(8, (target_count or 6) * 2))

        # Progressive fallback: if matches are sparse, relax constraints in priority order.
        if len(filtered) < desired_pool:
            filtered = _collect(use_include=False)
            if filtered:
                relaxation_note = "Relaxed must_include constraint to improve candidate coverage."
        if len(filtered) < desired_pool:
            filtered = _collect(use_include=False, use_year=False)
            if filtered:
                relaxation_note = "Relaxed include and year constraints to improve candidate coverage."
        if len(filtered) < desired_pool:
            filtered = _collect(use_include=False, use_year=False, use_energy=False, use_bpm=False)
            if filtered:
                relaxation_note = "Relaxed include, year, energy, and bpm constraints to improve candidate coverage."
        if len(filtered) < desired_pool:
            filtered = _collect(
                use_include=False,
                use_year=False,
                use_energy=False,
                use_bpm=False,
                use_genre=False,
            )
            if filtered:
                relaxation_note = "Returned broader next-best options with only exclusions enforced."

        filtered = _dedupe_by_track_artist(filtered)
        pre_cap = max(50, _coerce_int(pre_sample_size) or 400)
        if len(filtered) > pre_cap:
            filtered = random.sample(filtered, pre_cap)
            relaxation_note = (
                f"{relaxation_note} Randomly pre-sampled {pre_cap} tracks from a larger valid pool."
                if relaxation_note
                else f"Randomly pre-sampled {pre_cap} tracks from a larger valid pool."
            )

        # Keep output fields aligned with selected_fields when available
        default_fields = ["Trackname", "Artist", "Album", "Year", "Genre", "energy", "Filepath"]
        output_fields = [f for f in selected_fields if isinstance(f, str)] or default_fields
        for field in ["Trackname", "Artist", "Album", "Filepath"]:
            if field not in output_fields:
                output_fields.append(field)

        candidate_tracks = []
        for rec in filtered:
            row = {k: rec.get(k) for k in output_fields}
            if "energy" in row:
                row["energy"] = _normalize_energy_value(row.get("energy"))
            candidate_tracks.append(row)
        final_limit = max(10, _coerce_int(limit) or 120)
        if len(candidate_tracks) > final_limit:
            candidate_tracks = random.sample(candidate_tracks, final_limit)
            relaxation_note = (
                f"{relaxation_note} Randomly sampled to final limit of {final_limit}."
                if relaxation_note
                else f"Randomly sampled to final limit of {final_limit}."
            )

        out = {
            "applied_filters": {
                "genres": constraints.get("genres", []),
                "year_range": {"min": y_min, "max": y_max},
                "energy_range": {"min": e_min, "max": e_max},
                "tempo_bpm_range": {"min": b_min, "max": b_max},
                "must_include": constraints.get("must_include", []),
                "must_exclude": constraints.get("must_exclude", []),
            },
            "candidate_count": len(candidate_tracks),
            "candidate_tracks": candidate_tracks,
            "notes": relaxation_note,
        }
        return json.dumps(out)


# -------------------------
# analyze_relevant_data tool
# -------------------------

class AnalyzeRelevantDataInput(BaseModel):
    filtered_dataset_json: str = Field(
        ..., description="JSON string output from filter_dataset task/tool."
    )
    query_intake_json: str = Field(
        "",
        description="Optional JSON string output from query_intake to compare objective fit.",
    )


class AnalyzeRelevantDataTool(BaseTool):
    name: str = "analyze_relevant_data_tool"
    description: str = (
        "Analyze filtered candidate tracks and return distributions, gaps, and curation guidance."
    )
    args_schema: Type[BaseModel] = AnalyzeRelevantDataInput

    def _run(self, filtered_dataset_json: str, query_intake_json: str = "") -> str:
        filtered_obj = _safe_json_loads(filtered_dataset_json, fallback={})
        intake = _safe_json_loads(query_intake_json, fallback={}) if query_intake_json else {}

        tracks = filtered_obj.get("candidate_tracks", []) if isinstance(filtered_obj, dict) else []
        tracks = tracks if isinstance(tracks, list) else []
        tracks = _normalize_records([t for t in tracks if isinstance(t, dict)])

        genre_counts = Counter()
        year_counts = Counter()
        energy_bucket_counts = Counter()

        for rec in tracks:
            genre = str(rec.get("Genre", "")).strip()
            if genre:
                genre_counts[genre] += 1

            year = _to_int(rec.get("Year"))
            if year is not None:
                year_counts[str(year)] += 1

            e_bucket = _energy_bucket(rec.get("energy"))
            if e_bucket is not None:
                energy_bucket_counts[e_bucket] += 1

        insights: List[str] = []
        if tracks:
            insights.append(f"Filtered pool has {len(tracks)} candidate tracks.")
        if genre_counts:
            top_genre, top_count = genre_counts.most_common(1)[0]
            insights.append(f"Most represented genre is {top_genre} ({top_count} tracks).")
        if energy_bucket_counts:
            top_energy, top_count = energy_bucket_counts.most_common(1)[0]
            insights.append(f"Most represented energy bucket is {top_energy} ({top_count} tracks).")

        gaps: List[str] = []
        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        target_count = _coerce_int(constraints.get("target_track_count"))
        if isinstance(target_count, int) and len(tracks) < target_count:
            gaps.append(
                f"Candidate pool ({len(tracks)}) is smaller than target track count ({target_count})."
            )
        if len(genre_counts) <= 1 and len(tracks) > 5:
            gaps.append("Low genre diversity may reduce playlist variety.")

        guidance = [
            "Prioritize unique artists early to improve variety.",
            "Sequence tracks with gradual energy flow unless user requested constant intensity.",
            "Preserve objective-constrained genres/eras first, then optimize cohesion.",
        ]

        out = {
            "summary_insights": insights,
            "distribution": {
                "genres": dict(genre_counts),
                "years": dict(year_counts),
                "energy": dict(energy_bucket_counts),
            },
            "gaps_vs_objectives": gaps,
            "curation_guidance": guidance,
        }
        return json.dumps(out)


# -------------------------
# curate_playlist tool
# -------------------------

class CuratePlaylistInput(BaseModel):
    query_intake_json: str = Field(..., description="JSON string output from query_intake.")
    filtered_dataset_json: str = Field(..., description="JSON string output from filter_dataset.")
    analysis_json: str = Field(
        "",
        description="Optional JSON string output from analyze_relevant_data.",
    )


class CuratePlaylistTool(BaseTool):
    name: str = "curate_playlist_tool"
    description: str = (
        "Produce the final playlist JSON from intake constraints, filtered candidates, and analysis guidance."
    )
    args_schema: Type[BaseModel] = CuratePlaylistInput

    def _run(
        self,
        query_intake_json: str,
        filtered_dataset_json: str,
        analysis_json: str = "",
    ) -> str:
        intake = _safe_json_loads(query_intake_json, fallback={})
        filtered = _safe_json_loads(filtered_dataset_json, fallback={})
        _ = _safe_json_loads(analysis_json, fallback={}) if analysis_json else {}

        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        clarified_query = intake.get("clarified_query", "Curated playlist") if isinstance(intake, dict) else "Curated playlist"

        candidates = filtered.get("candidate_tracks", []) if isinstance(filtered, dict) else []
        candidates = candidates if isinstance(candidates, list) else []
        norm_candidates = _normalize_records([c for c in candidates if isinstance(c, dict)])

        target_count = _coerce_int(constraints.get("target_track_count"))
        if not isinstance(target_count, int) or target_count <= 0:
            target_count = min(20, max(10, len(norm_candidates))) if norm_candidates else 10

        # Prefer artist diversity first, then fill remainder.
        selected: List[Dict[str, Any]] = []
        used_artists = set()

        # Sort by year if available (fallback stable order)
        def sort_key(rec: Dict[str, Any]) -> Tuple[int, str]:
            y = _to_int(rec.get("Year"))
            return (y if y is not None else 9999, str(rec.get("Trackname", "")))

        ordered = sorted(norm_candidates, key=sort_key)

        for rec in ordered:
            artist = str(rec.get("Artist", "")).strip().lower()
            if artist and artist in used_artists:
                continue
            selected.append(rec)
            if artist:
                used_artists.add(artist)
            if len(selected) >= target_count:
                break

        if len(selected) < target_count:
            for rec in ordered:
                if rec in selected:
                    continue
                selected.append(rec)
                if len(selected) >= target_count:
                    break

        tracks_out = []
        for idx, rec in enumerate(selected, start=1):
            tracks_out.append(
                {
                    "position": idx,
                    "Trackname": rec.get("Trackname"),
                    "Artist": rec.get("Artist"),
                    "Album": rec.get("Album"),
                    "Year": rec.get("Year"),
                    "Genre": rec.get("Genre"),
                    "energy": _normalize_energy_value(rec.get("energy")),
                    "Filepath": rec.get("Filepath"),
                    "why_selected": "Matches constraints and supports playlist flow.",
                }
            )

        unmet = []
        if len(tracks_out) < target_count:
            unmet.append(
                f"Requested target_track_count={target_count}, but only {len(tracks_out)} candidates were available."
            )

        genre_set = sorted({str(t.get("Genre")) for t in tracks_out if t.get("Genre")})
        objective_fit_summary = [
            f"Selected {len(tracks_out)} tracks from filtered candidates.",
            f"Genre coverage: {', '.join(genre_set) if genre_set else 'limited/unknown'}.",
        ]

        playlist_title = f"SHRQ Playlist: {clarified_query[:60]}"

        out = {
            "playlist_title": playlist_title,
            "final_track_count": len(tracks_out),
            "tracks": tracks_out,
            "objective_fit_summary": objective_fit_summary,
            "unmet_constraints": unmet,
        }
        return json.dumps(out)


# -------------------------
# Backward-compatible aliases
# -------------------------
# Keep legacy names available so existing imports/usages do not break.
FilterTracksTool = FilterDatasetTool
AnalyzeTracksTool = AnalyzeRelevantDataTool
