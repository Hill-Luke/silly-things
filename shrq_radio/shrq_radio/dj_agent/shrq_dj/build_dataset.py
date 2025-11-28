import os
import json
from pathlib import Path
from mutagen.id3 import ID3, ID3NoHeaderError
import pandas as pd


def extract_tags_from_mp3(mp3_path: Path) -> dict:
    """Extract all ID3 tags from a single MP3 file."""
    data = {"filepath": str(mp3_path)}
    try:
        tags = ID3(mp3_path)
    except ID3NoHeaderError:
        # No tags at all
        return data

    for key, frame in tags.items():
        try:
            # Many ID3 frames store text as a list
            if hasattr(frame, "text"):
                value = frame.text
                if isinstance(value, list):
                    if len(value) == 0:
                        value = None
                    elif len(value) == 1:
                        value = value[0]
                    else:
                        # Join multi-value frames into a single string
                        value = "; ".join(str(v) for v in value)
                else:
                    value = str(value)
            else:
                # Fallback: stringify the frame
                value = str(frame)

            data[str(key)] = value
        except Exception:
            data[str(key)] = None

    return data


def build_mp3_dataset(root_folder: str) -> pd.DataFrame:
    root = Path(root_folder)
    rows = []

    for mp3_file in root.rglob("*.mp3"):
        row = extract_tags_from_mp3(mp3_file)
        rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    folder = input("Enter path to your music folder: ").strip()
    df = build_mp3_dataset(folder)
    print(df.head())

    # Convert DataFrame to list-of-dicts and write JSON with stdlib json
    records = df.to_dict(orient="records")

    with open("mp3_dataset.json", "w") as f:
        json.dump(records, f, indent=2, default=str)

    # If you want CSV too:
    # df.to_csv("mp3_dataset.csv", index=False)

    print("Dataset saved as mp3_dataset.json")