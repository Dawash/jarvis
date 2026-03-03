"""Web agent — fetches URLs, extracts content, searches the web."""

from typing import Any
import aiohttp
from bs4 import BeautifulSoup

from backend.agents.base_agent import BaseAgent
from backend.llm.tools import WEB_TOOLS


class WebAgent(BaseAgent):
    agent_type = "web"
    description = "Web browsing agent — fetches URLs, extracts text from web pages, performs web searches."

    @property
    def tools(self) -> list[dict]:
        return WEB_TOOLS

    async def execute_tool(self, name: str, inp: dict) -> Any:
        match name:
            case "fetch_url":
                return await self._fetch_url(inp["url"], inp.get("extract_text", True))
            case "web_search":
                return await self._web_search(inp["query"], inp.get("num_results", 5))
            case _:
                return f"Unknown tool: {name}"

    async def _fetch_url(self, url: str, extract_text: bool = True) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 JARVIS-Agent/1.0"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return f"HTTP {resp.status}: {resp.reason}"
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" in content_type and extract_text:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = soup.get_text(separator="\n", strip=True)
                        title = soup.title.string if soup.title else "No title"
                        return f"Title: {title}\n\n{text[:15000]}"
                    else:
                        raw = await resp.text()
                        return raw[:15000]
        except Exception as e:
            return f"Error fetching URL: {e}"

    async def _web_search(self, query: str, num_results: int = 5) -> str:
        """Search via DuckDuckGo HTML (no API key needed)."""
        try:
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data={"q": query}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    results = []
                    for r in soup.select(".result")[:num_results]:
                        title_el = r.select_one(".result__a")
                        snippet_el = r.select_one(".result__snippet")
                        link_el = r.select_one(".result__url")
                        title = title_el.get_text(strip=True) if title_el else ""
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                        link = link_el.get_text(strip=True) if link_el else ""
                        if title:
                            results.append(f"- {title}\n  {link}\n  {snippet}")
                    return "\n\n".join(results) if results else "No results found."
        except Exception as e:
            return f"Search error: {e}"
