import sys
import traceback
from mutagen.id3 import ID3, ID3NoHeaderError
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
import librosa
import numpy as np
import pyloudnorm as pyln
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import soundfile as sf
import os

import check_tags
import picard_clean
import energy_tagger
from tqdm import tqdm


def frame_text(frame):
    if frame is None:
        return None
    value = getattr(frame, "text", None)
    if isinstance(value, list) and value:
        return str(value[0])
    return str(frame)

def pre_process_mp3(i):
    try:
        try:
            tags = ID3(i)
        except ID3NoHeaderError:
            print(f"No ID3 header found in: {i}")
            return



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
                tags.save(i)
                print(f"[Updated tags from MusicBrainz] Saved changes to {i}")
            except Exception as save_err:
                print(f"Failed to save updated tags to {i}: {repr(save_err)}")

        # Final printout
        print(f"File: {i}")
        print(f"  Artist: {artist or 'N/A'}")
        print(f"  Genre:  {genre or 'N/A'}")
        print(f"  Album:  {album or 'N/A'}")
        print(f"  Year:   {year or 'N/A'}")
        print(f"  Energy: {energy or 'N/A'}")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error reading tags from {i}: {repr(e)}\nTraceback:\n{tb}")



    # ------------------------------------ #
    # Tag the Energy 
    # ------------------------------------ #
    
    energy_tagger.analyze_mp3(i)



if __name__ == "__main__":
    from pathlib import Path

    # Allow passing a file or folder path as a command-line argument, e.g.:
    #   python intake_mp3.py /path/to/file.mp3
    #   python intake_mp3.py /path/to/folder
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1]).expanduser()
    else:
        target_path = Path(input("Enter the path to the MP3 file or folder: ").strip()).expanduser()

    if not target_path.exists():
        print(f"Path does not exist: {target_path}")
        sys.exit(1)

    if target_path.is_file():
        pre_process_mp3(str(target_path))
    else:
        # Assume directory: walk all .mp3 files under it
        for mp3_file in tqdm(target_path.rglob("*.mp3")):
            pre_process_mp3(str(mp3_file))
