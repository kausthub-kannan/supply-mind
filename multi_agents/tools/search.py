import os
from typing import Literal

from tavily import TavilyClient
from langchain.tools import tool

from multi_agents.tools.schemas.search import SearchInput


from multi_agents.utils.logger import setup_logger

logger = setup_logger()


@tool(
    args_schema=SearchInput,
    return_direct=False,
)
def web_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    topic: Literal["general", "news"] = "general",
) -> list[dict]:
    """
    Tool used to perform web search using Tavily for given search query
    :param query: str - The string which is the query to be performed in web search
    :param max_results: int - Number of max results to be obtained from the search, by default 5
    :param include_domains: list - The domains from which the search needs to be done, by default no doamin is set
    :param topic: str - The topic to perform search upon. It can be either general or new, by default general
    :return: list - List search result content
    """
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

        logger.info(f"TAVILY SEARCH RESULTS: {response}")

        results = [
            {
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]

        return results or [{"error": "No results found", "query": query}]

    except KeyError:
        return [{"error": "TAVILY_API_KEY is not set in environment"}]
    except Exception as exc:
        return [{"error": str(exc), "query": query}]
