from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from pathlib import Path
import mimetypes
import json
from datetime import datetime


class FileScannerToolInput(BaseModel):
    """Input schema for FileScannerTool."""
    model_config = {"extra": "ignore"}
    folder: str = Field(..., description="Path to the folder to scan.")


class FileScannerTool(BaseTool):
    name: str = "File Scanner Tool"
    model_config = {"extra": "ignore"}
    description: str = (
        "Scans all files in a given folder recursively and returns details about each file."
    )
    args_schema: Type[BaseModel] = FileScannerToolInput

    def _run(self, folder: str) -> str:
        # Validate input folder
        folder_path = Path(folder).expanduser().resolve()
        if not folder_path.exists():
            return json.dumps({"error": f"Folder not found: {folder_path}"})
        if not folder_path.is_dir():
            return json.dumps({"error": f"Path is not a directory: {folder_path}"})

        results = []
        # Ensure mimetypes has common types initialized
        mimetypes.init()

        for file_path in folder_path.rglob("*"):
            try:
                if file_path.is_dir() or file_path.is_symlink():
                    continue
                mime_type, _ = mimetypes.guess_type(str(file_path))
                ext = file_path.suffix.lower()
                if mime_type:
                    category = mime_type.split("/")[0]
                elif ext:
                    category = ext.lstrip(".")
                else:
                    category = "unknown"
                stat = file_path.stat()
                modified_date = datetime.fromtimestamp(stat.st_mtime).isoformat()
                results.append({
                    "path": str(file_path),
                    "category": category,
                    "mime_type": mime_type or "unknown",
                    "size_bytes": stat.st_size,
                    "modified_date": modified_date,
                })
            except Exception as e:
                results.append({
                    "path": str(file_path),
                    "error": str(e)
                })

        return json.dumps(results, indent=2)
