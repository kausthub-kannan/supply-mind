from typing import Literal
from pydantic import BaseModel, Field


class SearchInput(BaseModel):
    query: str = Field(
        description="Concise search query to find up-to-date information",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results to return (1–10)",
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description="Restrict results to these domains, e.g. ['arxiv.org', 'docs.python.org']",
    )
    topic: Literal["general", "news"] = Field(
        default="general",
        description="'news' for recent articles, 'general' for broader web search",
    )
