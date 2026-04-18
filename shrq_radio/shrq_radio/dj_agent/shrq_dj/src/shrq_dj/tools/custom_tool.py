from typing import Type, List, Dict, Any, Optional, Tuple

import json
import re
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
}

KNOWN_GENRES = [
    "pop", "rock", "hip hop", "rap", "r&b", "jazz", "blues", "country", "folk",
    "electronic", "edm", "house", "techno", "drum and bass", "indie", "metal",
    "punk", "classical", "latin", "reggaeton", "soul", "funk", "disco", "lofi",
]


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
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


def _extract_energy_range(query: str) -> Tuple[Optional[float], Optional[float]]:
    q = query.lower()
    if any(word in q for word in ["chill", "calm", "ambient", "soft", "relax"]):
        return 0.0, 0.45
    if any(word in q for word in ["high energy", "energetic", "hype", "workout", "intense"]):
        return 0.65, 1.0
    if any(word in q for word in ["mid energy", "moderate", "balanced"]):
        return 0.35, 0.75
    return None, None


def _extract_bpm_range(query: str) -> Tuple[Optional[float], Optional[float]]:
    q = query.lower()
    range_match = re.search(r"\b(\d{2,3})\s*[-to]{1,3}\s*(\d{2,3})\s*bpm\b", q)
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

    # Simple phrase-based parsing
    for pat in [r"without\s+([a-z0-9&\-\s]+)", r"no\s+([a-z0-9&\-\s]+)"]:
        for m in re.findall(pat, q):
            token = m.strip().split(",")[0].strip()
            if token:
                must_exclude.append(token)

    for pat in [r"include\s+([a-z0-9&\-\s]+)", r"must have\s+([a-z0-9&\-\s]+)"]:
        for m in re.findall(pat, q):
            token = m.strip().split(",")[0].strip()
            if token:
                must_include.append(token)

    return list(dict.fromkeys(must_include)), list(dict.fromkeys(must_exclude))


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
        for k in ["Trackname", "Artist", "Album", "Genre", "Year"]
    ).lower()


# -------------------------
# query_intake tool
# -------------------------

class QueryIntakeInput(BaseModel):
    query: str = Field(..., description="Raw user query requesting playlist curation.")


class QueryIntakeTool(BaseTool):
    name: str = "query_intake_tool"
    description: str = (
        "Turn a raw playlist query into structured JSON with clarified intent, "
        "playlist objectives, and constraints."
    )
    args_schema: Type[BaseModel] = QueryIntakeInput

    def _run(self, query: str) -> str:
        q = query.strip()
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
        ..., description="JSON output from query_intake task/tool."
    )
    records: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional dataset records to detect available fields.",
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
        records: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        intake = _safe_json_loads(query_intake_json, fallback={})
        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}

        available = set()
        if records:
            norm = _normalize_records(records[:25])
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
    records: List[Dict[str, Any]] = Field(..., description="Full dataset records.")
    query_intake_json: str = Field(..., description="JSON output from query_intake.")
    selected_fields_json: Optional[str] = Field(
        None,
        description="JSON output from select_relevant_fields.",
    )
    limit: Optional[int] = Field(
        300,
        description="Maximum number of candidate records to return.",
    )


class FilterDatasetTool(BaseTool):
    name: str = "filter_dataset_tool"
    description: str = (
        "Filter dataset records using constraints derived from query intake and selected fields."
    )
    args_schema: Type[BaseModel] = FilterDatasetInput

    def _run(
        self,
        records: List[Dict[str, Any]],
        query_intake_json: str,
        selected_fields_json: Optional[str] = None,
        limit: Optional[int] = 300,
    ) -> str:
        intake = _safe_json_loads(query_intake_json, fallback={})
        selected_obj = _safe_json_loads(selected_fields_json, fallback={}) if selected_fields_json else {}

        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        selected_fields = selected_obj.get("selected_fields", []) if isinstance(selected_obj, dict) else []
        selected_fields = selected_fields if isinstance(selected_fields, list) else []

        genres = [str(g).lower() for g in constraints.get("genres", [])]
        year_range = constraints.get("year_range", {}) if isinstance(constraints.get("year_range", {}), dict) else {}
        energy_range = constraints.get("energy_range", {}) if isinstance(constraints.get("energy_range", {}), dict) else {}
        bpm_range = constraints.get("tempo_bpm_range", {}) if isinstance(constraints.get("tempo_bpm_range", {}), dict) else {}
        must_include = [str(x).lower() for x in constraints.get("must_include", [])]
        must_exclude = [str(x).lower() for x in constraints.get("must_exclude", [])]

        y_min = _to_int(year_range.get("min"))
        y_max = _to_int(year_range.get("max"))
        e_min = _to_float(energy_range.get("min"))
        e_max = _to_float(energy_range.get("max"))
        b_min = _to_float(bpm_range.get("min"))
        b_max = _to_float(bpm_range.get("max"))

        norm_records = _normalize_records(records)
        filtered: List[Dict[str, Any]] = []

        for rec in norm_records:
            text = _record_text(rec)

            if genres:
                rec_genre = str(rec.get("Genre", "")).lower()
                if not any(g in rec_genre for g in genres):
                    continue

            year_val = _to_int(rec.get("Year"))
            if y_min is not None and (year_val is None or year_val < y_min):
                continue
            if y_max is not None and (year_val is None or year_val > y_max):
                continue

            energy_val = _to_float(rec.get("energy"))
            if e_min is not None and (energy_val is None or energy_val < e_min):
                continue
            if e_max is not None and (energy_val is None or energy_val > e_max):
                continue

            bpm_val = _to_float(rec.get("bpm"))
            if b_min is not None and (bpm_val is None or bpm_val < b_min):
                continue
            if b_max is not None and (bpm_val is None or bpm_val > b_max):
                continue

            if must_exclude and any(token in text for token in must_exclude):
                continue

            if must_include and not any(token in text for token in must_include):
                continue

            filtered.append(rec)

            if limit is not None and len(filtered) >= limit:
                break

        filtered = _dedupe_by_track_artist(filtered)

        # Keep output fields aligned with selected_fields when available
        default_fields = ["Trackname", "Artist", "Album", "Year", "Genre", "energy"]
        output_fields = [f for f in selected_fields if isinstance(f, str)] or default_fields
        for field in ["Trackname", "Artist", "Album"]:
            if field not in output_fields:
                output_fields.append(field)

        candidate_tracks = [
            {k: rec.get(k) for k in output_fields}
            for rec in filtered
        ]

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
            "notes": "Strict filtering applied from parsed constraints.",
        }
        return json.dumps(out)


# -------------------------
# analyze_relevant_data tool
# -------------------------

class AnalyzeRelevantDataInput(BaseModel):
    filtered_dataset_json: str = Field(
        ..., description="JSON output from filter_dataset task/tool."
    )
    query_intake_json: Optional[str] = Field(
        None,
        description="Optional JSON output from query_intake to compare objective fit.",
    )


class AnalyzeRelevantDataTool(BaseTool):
    name: str = "analyze_relevant_data_tool"
    description: str = (
        "Analyze filtered candidate tracks and return distributions, gaps, and curation guidance."
    )
    args_schema: Type[BaseModel] = AnalyzeRelevantDataInput

    def _run(self, filtered_dataset_json: str, query_intake_json: Optional[str] = None) -> str:
        filtered_obj = _safe_json_loads(filtered_dataset_json, fallback={})
        intake = _safe_json_loads(query_intake_json, fallback={}) if query_intake_json else {}

        tracks = filtered_obj.get("candidate_tracks", []) if isinstance(filtered_obj, dict) else []
        tracks = tracks if isinstance(tracks, list) else []
        tracks = _normalize_records([t for t in tracks if isinstance(t, dict)])

        genre_counts = Counter()
        year_counts = Counter()
        energy_counts = {"low": 0, "mid": 0, "high": 0}
        energies: List[float] = []

        for rec in tracks:
            genre = str(rec.get("Genre", "")).strip()
            if genre:
                genre_counts[genre] += 1

            year = _to_int(rec.get("Year"))
            if year is not None:
                year_counts[str(year)] += 1

            e = _to_float(rec.get("energy"))
            if e is not None:
                energies.append(e)
                if e < 0.34:
                    energy_counts["low"] += 1
                elif e <= 0.66:
                    energy_counts["mid"] += 1
                else:
                    energy_counts["high"] += 1

        insights: List[str] = []
        if tracks:
            insights.append(f"Filtered pool has {len(tracks)} candidate tracks.")
        if genre_counts:
            top_genre, top_count = genre_counts.most_common(1)[0]
            insights.append(f"Most represented genre is {top_genre} ({top_count} tracks).")
        if energies:
            avg_energy = sum(energies) / len(energies)
            insights.append(f"Average candidate energy is {avg_energy:.2f}.")

        gaps: List[str] = []
        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        target_count = constraints.get("target_track_count")
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
                "energy": energy_counts,
            },
            "gaps_vs_objectives": gaps,
            "curation_guidance": guidance,
        }
        return json.dumps(out)


# -------------------------
# curate_playlist tool
# -------------------------

class CuratePlaylistInput(BaseModel):
    query_intake_json: str = Field(..., description="JSON output from query_intake.")
    filtered_dataset_json: str = Field(..., description="JSON output from filter_dataset.")
    analysis_json: Optional[str] = Field(
        None,
        description="Optional JSON output from analyze_relevant_data.",
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
        analysis_json: Optional[str] = None,
    ) -> str:
        intake = _safe_json_loads(query_intake_json, fallback={})
        filtered = _safe_json_loads(filtered_dataset_json, fallback={})
        _ = _safe_json_loads(analysis_json, fallback={}) if analysis_json else {}

        constraints = intake.get("constraints", {}) if isinstance(intake, dict) else {}
        clarified_query = intake.get("clarified_query", "Curated playlist") if isinstance(intake, dict) else "Curated playlist"

        candidates = filtered.get("candidate_tracks", []) if isinstance(filtered, dict) else []
        candidates = candidates if isinstance(candidates, list) else []
        norm_candidates = _normalize_records([c for c in candidates if isinstance(c, dict)])

        target_count = constraints.get("target_track_count")
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
                    "energy": rec.get("energy"),
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
