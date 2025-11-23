# This is a scratch file to check the tags of an mp3 file for artist, genre, year, energy.
import sys
import traceback

from mutagen.id3 import (
    ID3,
    ID3NoHeaderError,
    TPE1,
    TCON,
    TALB,
    TDRC,
    TYER,
    TIT2,
)

import musicbrainzngs as mb

# Configure MusicBrainz client (replace email with your own if you like)
mb.set_useragent("dj-tag-cleaner", "0.1", "your-email@example.com")


def print_tags(filepath: str) -> None:
    """Print selected ID3 tags for the given MP3 file.

    Prints: artist, genre, album, year, and custom 'energy' tag (if present).
    If any of artist/genre/album/year are missing, attempts to backfill only
    those four fields from MusicBrainz (Picard-style) using existing tags
    (primarily title/artist) and then saves updated tags back to the file.

    Note: the 'energy' tag is treated as a user-defined field and is never
    queried from or overwritten by MusicBrainz.
    """
    try:
        try:
            tags = ID3(filepath)
        except ID3NoHeaderError:
            print(f"No ID3 header found in: {filepath}")
            return

        def frame_text(frame):
            if frame is None:
                return None
            value = getattr(frame, "text", None)
            if isinstance(value, list) and value:
                return str(value[0])
            return str(frame)

        # Read existing tags
        artist = frame_text(tags.get("TPE1"))  # Lead performer/soloist
        genre = frame_text(tags.get("TCON"))   # Content type (genre)
        album = frame_text(tags.get("TALB"))   # Album/Movie/Show title

        # Year can be stored in different frames depending on ID3 version
        year = None
        year_frame = tags.get("TDRC") or tags.get("TYER")
        if year_frame is not None:
            year = frame_text(year_frame)

        # Custom 'energy' tag stored in a TXXX frame with desc="energy"
        # Note: we deliberately never backfill or overwrite this from MusicBrainz.
        energy = None
        for key, frame in tags.items():
            if key.startswith("TXXX:") and getattr(frame, "desc", "").lower() == "energy":
                value = getattr(frame, "text", None)
                if isinstance(value, list) and value:
                    energy = str(value[0])
                else:
                    energy = str(frame)
                break

        # Keep originals to decide whether anything changed
        orig_artist, orig_genre, orig_album, orig_year = artist, genre, album, year

        # Helper to attempt MusicBrainz backfill
        def backfill_with_musicbrainz(artist_val, genre_val, album_val, year_val):
            # Only bother if anything is missing
            if all([artist_val, genre_val, album_val, year_val]):
                return artist_val, genre_val, album_val, year_val

            title = frame_text(tags.get("TIT2"))  # Track title
            # We need at least a title or artist to search
            if not title and not artist_val:
                return artist_val, genre_val, album_val, year_val

            try:
                search_kwargs = {}
                if title:
                    search_kwargs["recording"] = title
                if artist_val:
                    search_kwargs["artist"] = artist_val

                result = mb.search_recordings(limit=1, **search_kwargs)
                recordings = result.get("recording-list", [])
                if not recordings:
                    return artist_val, genre_val, album_val, year_val

                rec = recordings[0]

                # Artist
                if not artist_val:
                    credits = rec.get("artist-credit", [])
                    names = []
                    for c in credits:
                        if isinstance(c, dict) and "artist" in c:
                            names.append(c["artist"]["name"])
                    if names:
                        artist_val = ", ".join(names)

                # Album + year (from first release)
                releases = rec.get("release-list", [])
                if releases:
                    rel = releases[0]
                    if not album_val:
                        album_val = rel.get("title", album_val)
                    if not year_val:
                        date = rel.get("date")
                        if date:
                            year_val = date[:4]

                    # Genre from tags on release if not set
                    if not genre_val:
                        tag_list = rel.get("tag-list", [])
                        if tag_list:
                            # Take the most popular / first tag name
                            name = tag_list[0].get("name")
                            if name:
                                genre_val = name

                return artist_val, genre_val, album_val, year_val

            except Exception as e2:
                # Don't crash the script if MusicBrainz fails
                print(f"MusicBrainz lookup failed: {repr(e2)}")
                return artist_val, genre_val, album_val, year_val

        # Try to backfill missing fields from MusicBrainz
        artist, genre, album, year = backfill_with_musicbrainz(artist, genre, album, year)

        # If anything changed, update ID3 tags and save
        updated = False

        if artist and artist != orig_artist:
            tags.setall("TPE1", [TPE1(encoding=3, text=artist)])
            updated = True

        if genre and genre != orig_genre:
            tags.setall("TCON", [TCON(encoding=3, text=genre)])
            updated = True

        if album and album != orig_album:
            tags.setall("TALB", [TALB(encoding=3, text=album)])
            updated = True

        if year and year != orig_year:
            # Prefer modern TDRC frame for date/year
            tags.setall("TDRC", [TDRC(encoding=3, text=str(year))])
            updated = True

        if updated:
            try:
                tags.save(filepath)
                print(f"[Updated tags from MusicBrainz] Saved changes to {filepath}")
            except Exception as save_err:
                print(f"Failed to save updated tags to {filepath}: {repr(save_err)}")

        # Final printout
        print(f"File: {filepath}")
        print(f"  Artist: {artist or 'N/A'}")
        print(f"  Genre:  {genre or 'N/A'}")
        print(f"  Album:  {album or 'N/A'}")
        print(f"  Year:   {year or 'N/A'}")
        print(f"  Energy: {energy or 'N/A'}")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error reading tags from {filepath}: {repr(e)}\nTraceback:\n{tb}")


if __name__ == "__main__":
    # Allow passing the filepath as a command-line argument, e.g.:
    #   python check_tags.py /path/to/file.mp3
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = input("Enter the path to the MP3 file: ")

    print_tags(filepath)





#!/usr/bin/env python3
"""picard_clean.py

Simple helper script that takes an MP3 filepath, looks it up on
MusicBrainz, and fills/overwrites core ID3 tags (title, artist,
album, year, genre) from the best match.

It intentionally **does not** touch any custom user tags such as a
TXXX frame with desc="energy".
"""

import os
import sys
import traceback
from typing import Optional

from mutagen.id3 import (
    ID3,
    ID3NoHeaderError,
    TIT2,
    TPE1,
    TALB,
    TCON,
    TDRC,
)

import musicbrainzngs as mb


# Configure MusicBrainz client (replace email with your own)
mb.set_useragent("dj-tag-cleaner", "0.2", "your-email@example.com")


def _frame_text(frame) -> Optional[str]:
    """Safely extract text from a mutagen frame, if present."""
    if frame is None:
        return None
    value = getattr(frame, "text", None)
    if isinstance(value, list) and value:
        return str(value[0])
    if value is not None:
        return str(value)
    return None


def lookup_musicbrainz(title: str, artist: Optional[str] = None) -> Optional[dict]:
    """Search MusicBrainz for a recording and return the best match dict.

    Currently this just takes the first result (limit=1).
    """
    search_kwargs = {"recording": title}
    if artist:
        search_kwargs["artist"] = artist

    print(f"[MB] Searching for recording={title!r}, artist={artist!r}...")
    result = mb.search_recordings(limit=1, **search_kwargs)
    recordings = result.get("recording-list", [])
    if not recordings:
        print("[MB] No recordings found.")
        return None

    rec = recordings[0]
    print(
        "[MB] Using match:",
        rec.get("title"),
        "-",
        ", ".join(
            c["artist"]["name"]
            for c in rec.get("artist-credit", [])
            if isinstance(c, dict) and "artist" in c
        )
        or "<unknown artist>",
    )
    return rec


def apply_mb_tags(filepath: str) -> None:
    """Look up `filepath` on MusicBrainz and write core tags from the result.

    Core tags we update:
      - Title  -> TIT2
      - Artist -> TPE1
      - Album  -> TALB
      - Year   -> TDRC (4-digit year from release date)
      - Genre  -> TCON (from first release tag, if present)

    We do **not** touch any custom TXXX frames (including a user-defined
    "energy" tag, if you use one).
    """
    try:
        # Try to load existing ID3 tags; if none, start fresh
        try:
            tags = ID3(filepath)
        except ID3NoHeaderError:
            tags = ID3()

        # Use existing tags as search hints where possible
        existing_title = _frame_text(tags.get("TIT2"))
        existing_artist = _frame_text(tags.get("TPE1"))

        if not existing_title:
            # Fall back to filename if we have no title tag
            existing_title = os.path.splitext(os.path.basename(filepath))[0]

        rec = lookup_musicbrainz(existing_title, existing_artist)
        if rec is None:
            print("No MusicBrainz match, nothing updated.")
            return

        # --- Extract data from the MusicBrainz recording ---
        new_title: Optional[str] = rec.get("title")

        # Artist from artist-credit
        artist_credits = rec.get("artist-credit", [])
        artist_names = []
        for c in artist_credits:
            if isinstance(c, dict) and "artist" in c:
                artist_names.append(c["artist"]["name"])
        new_artist: Optional[str] = ", ".join(artist_names) if artist_names else existing_artist

        new_album: Optional[str] = None
        new_year: Optional[str] = None
        new_genre: Optional[str] = None

        releases = rec.get("release-list", [])
        if releases:
            rel = releases[0]
            new_album = rel.get("title") or new_album

            date = rel.get("date")
            if date:
                new_year = date[:4]

            tag_list = rel.get("tag-list", [])
            if tag_list:
                name = tag_list[0].get("name")
                if name:
                    new_genre = name

        # --- Apply tags to the file ---
        if new_title:
            tags.setall("TIT2", [TIT2(encoding=3, text=new_title)])
        if new_artist:
            tags.setall("TPE1", [TPE1(encoding=3, text=new_artist)])
        if new_album:
            tags.setall("TALB", [TALB(encoding=3, text=new_album)])
        if new_genre:
            tags.setall("TCON", [TCON(encoding=3, text=new_genre)])
        if new_year:
            tags.setall("TDRC", [TDRC(encoding=3, text=str(new_year))])

        # Save updated tags back to the file
        tags.save(filepath)

        print("\n[Updated tags]")
        print(f"  File : {filepath}")
        print(f"  Title: {new_title or existing_title}")
        print(f"  Artist: {new_artist or existing_artist or 'N/A'}")
        print(f"  Album: {new_album or 'N/A'}")
        print(f"  Year: {new_year or 'N/A'}")
        print(f"  Genre: {new_genre or 'N/A'}")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error processing {filepath}: {e}\nTraceback:\n{tb}")


def main() -> None:
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = input("Enter the path to the MP3 file: ").strip()

    if not filepath:
        print("No filepath provided.")
        return

    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}")
        return

    apply_mb_tags(filepath)


if __name__ == "__main__":
    main()