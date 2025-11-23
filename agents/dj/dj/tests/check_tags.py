# This is a scratch file to check the tags of an mp3 file for artist, genre, year, energy.
import sys
import traceback
from mutagen.id3 import ID3, ID3NoHeaderError


def print_tags(filepath: str) -> None:
    """Print selected ID3 tags for the given MP3 file.

    Prints: artist, genre, album, year, and custom 'energy' tag (if present).
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
            # Most text frames have a .text list; take the first element
            value = getattr(frame, "text", None)
            if isinstance(value, list) and value:
                return str(value[0])
            return str(frame)

        # Standard frames
        artist = frame_text(tags.get("TPE1"))  # Lead performer/soloist
        genre = frame_text(tags.get("TCON"))   # Content type (genre)
        album = frame_text(tags.get("TALB"))   # Album/Movie/Show title

        # Year can be stored in different frames depending on ID3 version
        year = None
        year_frame = tags.get("TDRC") or tags.get("TYER")
        if year_frame is not None:
            year = frame_text(year_frame)

        # Custom 'energy' tag stored in a TXXX frame with desc="energy"
        energy = None
        for key, frame in tags.items():
            if key.startswith("TXXX:") and getattr(frame, "desc", "").lower() == "energy":
                value = getattr(frame, "text", None)
                if isinstance(value, list) and value:
                    energy = str(value[0])
                else:
                    energy = str(frame)
                break

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




