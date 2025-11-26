from typing import Type, List, Dict, Any, Optional

import json
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# -------------------------
# Example placeholder tool
# -------------------------

class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")


class MyCustomTool(BaseTool):
    name: str = "example_tool"
    description: str = (
        "Example tool implementation. This is a placeholder and not used for filtering."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        # Implementation goes here
        return f"You passed: {argument}. This is an example tool output."


# ----------------------------------
# Filtering tool for track records
# ----------------------------------

class FilterTracksInput(BaseModel):
    """Input schema for filtering a list of track records."""

    records: List[Dict[str, Any]] = Field(
        ...,
        description=(
            "List of track records (dicts) to filter. Each record should at least contain "
            "fields like artist, title, genre, year, bpm, and energy where available."
        ),
    )
    artist: Optional[str] = Field(
        None,
        description="If provided, only keep tracks whose artist name contains this string (case-insensitive).",
    )
    genre: Optional[str] = Field(
        None,
        description="If provided, only keep tracks whose genre contains this string (case-insensitive).",
    )
    min_year: Optional[int] = Field(
        None,
        description="If provided, only keep tracks with year >= this value.",
    )
    max_year: Optional[int] = Field(
        None,
        description="If provided, only keep tracks with year <= this value.",
    )
    min_bpm: Optional[float] = Field(
        None,
        description="If provided, only keep tracks with bpm >= this value (if bpm is present).",
    )
    max_bpm: Optional[float] = Field(
        None,
        description="If provided, only keep tracks with bpm <= this value (if bpm is present).",
    )
    min_energy: Optional[float] = Field(
        None,
        description="If provided, only keep tracks with energy >= this value (if energy is present).",
    )
    max_energy: Optional[float] = Field(
        None,
        description="If provided, only keep tracks with energy <= this value (if energy is present).",
    )
    limit: Optional[int] = Field(
        100,
        description="Maximum number of records to return after filtering (to keep responses manageable).",
    )


class FilterTracksTool(BaseTool):
    """Tool to filter a list of track dicts based on simple criteria."""

    name: str = "filter_tracks"
    description: str = (
        "Filter a list of track records (dicts) by artist, genre, year range, bpm range, "
        "and energy range. Returns a JSON array of the filtered records (truncated to `limit`)."
    )
    args_schema: Type[BaseModel] = FilterTracksInput

    def _run(
        self,
        records: List[Dict[str, Any]],
        artist: Optional[str] = None,
        genre: Optional[str] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_bpm: Optional[float] = None,
        max_bpm: Optional[float] = None,
        min_energy: Optional[float] = None,
        max_energy: Optional[float] = None,
        limit: Optional[int] = 100,
    ) -> str:
        """Filter track records according to the provided criteria and return them as JSON."""

        def get_num(record: Dict[str, Any], key: str) -> Optional[float]:
            value = record.get(key)
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def get_int(record: Dict[str, Any], key: str) -> Optional[int]:
            value = record.get(key)
            try:
                if value is None:
                    return None
                return int(value)
            except (TypeError, ValueError):
                return None

        filtered: List[Dict[str, Any]] = []

        artist_lower = artist.lower() if artist else None
        genre_lower = genre.lower() if genre else None

        for rec in records:
            # Artist filter
            if artist_lower is not None:
                rec_artist = str(rec.get("artist", ""))
                if artist_lower not in rec_artist.lower():
                    continue

            # Genre filter
            if genre_lower is not None:
                rec_genre = str(rec.get("genre", ""))
                if genre_lower not in rec_genre.lower():
                    continue

            # Year filters
            year_val = get_int(rec, "year")
            if min_year is not None and (year_val is None or year_val < min_year):
                continue
            if max_year is not None and (year_val is None or year_val > max_year):
                continue

            # BPM filters
            bpm_val = get_num(rec, "bpm")
            if min_bpm is not None and (bpm_val is None or bpm_val < min_bpm):
                continue
            if max_bpm is not None and (bpm_val is None or bpm_val > max_bpm):
                continue

            # Energy filters
            energy_val = get_num(rec, "energy")
            if min_energy is not None and (energy_val is None or energy_val < min_energy):
                continue
            if max_energy is not None and (energy_val is None or energy_val > max_energy):
                continue

            filtered.append(rec)

            if limit is not None and len(filtered) >= limit:
                break

        return json.dumps(filtered)


# ----------------------------------
# Analysis tool for track records
# ----------------------------------

class AnalyzeTracksInput(BaseModel):
    """Input schema for analyzing a list of track records."""

    records: List[Dict[str, Any]] = Field(
        ..., description="List of track records (dicts) to analyze."
    )
    group_by: Optional[str] = Field(
        None,
        description=(
            "Optional field name to group by (e.g., 'artist' or 'genre') and count occurrences."
        ),
    )


class AnalyzeTracksTool(BaseTool):
    """Tool to compute simple aggregate stats over track records."""

    name: str = "analyze_tracks"
    description: str = (
        "Analyze a list of track records (dicts) to compute simple statistics such as "
        "counts, optional group-by counts, and min/max of numeric fields like bpm and energy."
    )
    args_schema: Type[BaseModel] = AnalyzeTracksInput

    def _run(
        self,
        records: List[Dict[str, Any]],
        group_by: Optional[str] = None,
    ) -> str:
        """Analyze tracks and return summary statistics as JSON."""

        summary: Dict[str, Any] = {}

        total = len(records)
        summary["total_records"] = total

        # Helper to safely coerce numeric fields
        def safe_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        # Collect numeric stats for bpm and energy if present
        bpms: List[float] = []
        energies: List[float] = []

        for rec in records:
            bpm_val = safe_float(rec.get("bpm"))
            if bpm_val is not None:
                bpms.append(bpm_val)

            energy_val = safe_float(rec.get("energy"))
            if energy_val is not None:
                energies.append(energy_val)

        if bpms:
            summary["bpm_min"] = min(bpms)
            summary["bpm_max"] = max(bpms)
            summary["bpm_avg"] = sum(bpms) / len(bpms)

        if energies:
            summary["energy_min"] = min(energies)
            summary["energy_max"] = max(energies)
            summary["energy_avg"] = sum(energies) / len(energies)

        # Optional group-by counts
        if group_by:
            counts: Dict[str, int] = {}
            for rec in records:
                key_val = rec.get(group_by)
                if key_val is None:
                    continue
                key_str = str(key_val)
                counts[key_str] = counts.get(key_str, 0) + 1
            summary["group_by"] = {
                "field": group_by,
                "counts": counts,
            }

        return json.dumps(summary)