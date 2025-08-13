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
