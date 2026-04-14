import os
from typing import Literal

from tavily import TavilyClient
from langchain.tools import tool

from schemas.search import SearchInput

@tool(
    "web_search",
    args_schema=SearchInput,
    return_direct=False,
)
def web_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    topic: Literal["general", "news"] = "general",
) -> list[dict]:
    try:
        client = TavilyClient(os.environ["TAVILY_API_KEY"])

        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=include_domains or [],
            topic=topic,
            include_answer=False,
            include_raw_content=False,
        )

        results = [
            {
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("content", ""),   # snippet / summary
                "score":   round(r.get("score", 0.0), 4),
            }
            for r in response.get("results", [])
        ]

        return results or [{"error": "No results found", "query": query}]

    except KeyError:
        return [{"error": "TAVILY_API_KEY is not set in environment"}]
    except Exception as exc:
        return [{"error": str(exc), "query": query}]