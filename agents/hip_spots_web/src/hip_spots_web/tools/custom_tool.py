from crewai.tools import BaseTool
from typing import Type, List
from pydantic import BaseModel, Field
import json
import sys


class DuckDuckGoInput(BaseModel):
    """Input schema for DuckDuckGoTool."""
    query: str = Field(..., description="Search query string.")

class DuckDuckGoTool(BaseTool):
    name: str = "DuckDuckGo Web Search"
    description: str = (
        "Free web search using DuckDuckGo. Input a query; returns JSON list of results with title, href, and snippet."
    )
    args_schema: Type[BaseModel] = DuckDuckGoInput

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
        except Exception as e:
            return f"duckduckgo-search import failed in interpreter {sys.executable}: {e}"

        results: List[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=8):
                    results.append({
                        "title": r.get("title"),
                        "href": r.get("href"),
                        "snippet": r.get("body") or r.get("snippet"),
                    })
        except Exception as e:
            return f"DDG search error: {e}"

        return json.dumps(results, ensure_ascii=False)
    

import requests
import json

class OSMInput(BaseModel):
    """Input schema for OpenStreetMapTool."""
    query: str = Field(..., description="Place name and city to search in OpenStreetMap")

class OpenStreetMapTool(BaseTool):
    name: str = "OpenStreetMap Search"
    description: str = (
        "Searches OpenStreetMap via the Nominatim API. Input a place name and city; "
        "returns JSON list of results with name, display_name, lat, lon."
    )
    args_schema: Type[BaseModel] = OSMInput

    def _run(self, query: str) -> str:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 5
        }
        try:
            headers = {"User-Agent": "hip-spots-web/1.0 (your_email@example.com)"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

        # Extract only relevant info
        results: List[dict] = []
        for r in data:
            results.append({
                "name": r.get("display_name"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "type": r.get("type"),
            })

        return json.dumps(results, ensure_ascii=False)
