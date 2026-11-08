"""Thin wrapper around the Anthropic Messages API with the server-side web_search tool.

Keeps the API key on the server, enforces a timeout, follows `pause_turn`, and returns
the text plus the list of URLs the search tool actually returned (used later to reject
fabricated citations).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from .. import config


class ResearchProviderError(Exception):
    """Raised for provider/configuration/network failures. The message is user-visible."""


@dataclass
class LLMResult:
    text: str
    search_results: list[dict] = field(default_factory=list)  # {url, title, page_age}
    cited_urls: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    web_search_requests: int = 0
    llm_calls: int = 1
    stop_reason: Optional[str] = None
    search_errors: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_searches: Optional[int]) -> LLMResult: ...


class AnthropicResearchClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key if api_key is not None else config.ANTHROPIC_API_KEY
        if not key:
            raise ResearchProviderError(
                "Research provider not configured: ANTHROPIC_API_KEY is not set on the server."
            )
        import anthropic

        self._anthropic = anthropic
        self.model = model or config.RESEARCH_MODEL
        self.client = anthropic.Anthropic(
            api_key=key, timeout=config.RESEARCH_TIMEOUT_SECONDS, max_retries=1
        )

    def complete(self, system: str, user: str, max_searches: Optional[int]) -> LLMResult:
        a = self._anthropic
        tools = []
        if max_searches:
            tools = [{"type": config.WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": max_searches}]
        messages: list[dict] = [{"role": "user", "content": user}]
        result = LLMResult(text="", llm_calls=0)
        text_parts: list[str] = []
        try:
            for _ in range(4):  # initial call + up to 3 pause_turn continuations
                kwargs = dict(
                    model=self.model,
                    max_tokens=config.RESEARCH_MAX_TOKENS,
                    system=system,
                    messages=messages,
                    output_config={"effort": config.RESEARCH_EFFORT},
                )
                if tools:
                    kwargs["tools"] = tools
                resp = self.client.messages.create(**kwargs)
                result.llm_calls += 1
                self._accumulate(resp, result, text_parts)
                result.stop_reason = resp.stop_reason
                if resp.stop_reason == "pause_turn":
                    messages = [
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]},
                    ]
                    text_parts = []  # the continued turn re-emits the final answer
                    continue
                break
        except a.APITimeoutError as e:
            raise ResearchProviderError(f"Research timed out after {config.RESEARCH_TIMEOUT_SECONDS:.0f}s.") from e
        except a.AuthenticationError as e:
            raise ResearchProviderError("Research provider rejected the API key (401).") from e
        except a.RateLimitError as e:
            raise ResearchProviderError("Research provider rate limit reached (429). Try again shortly.") from e
        except a.BadRequestError as e:
            raise ResearchProviderError(f"Research request rejected (400): {getattr(e, 'message', e)}") from e
        except a.APIStatusError as e:
            raise ResearchProviderError(f"Research provider error ({e.status_code}).") from e
        except a.APIConnectionError as e:
            raise ResearchProviderError("Could not reach the research provider (network error).") from e
        if result.stop_reason == "refusal":
            raise ResearchProviderError("The model declined this request (refusal).")
        result.text = "".join(text_parts).strip()
        return result

    @staticmethod
    def _accumulate(resp, result: LLMResult, text_parts: list[str]) -> None:
        usage = resp.usage
        result.input_tokens += usage.input_tokens or 0
        result.output_tokens += usage.output_tokens or 0
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            result.web_search_requests += getattr(stu, "web_search_requests", 0) or 0
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        result.cited_urls.append(url)
            elif btype == "server_tool_use" and getattr(block, "name", "") == "web_search":
                q = (getattr(block, "input", None) or {}).get("query")
                if q:
                    result.search_queries.append(q)
            elif btype == "web_search_tool_result":
                content = block.content
                if isinstance(content, list):
                    for r in content:
                        result.search_results.append(
                            {"url": r.url, "title": getattr(r, "title", None), "page_age": getattr(r, "page_age", None)}
                        )
                else:  # error object, HTTP 200
                    result.search_errors.append(getattr(content, "error_code", "unknown_error"))


def estimate_cost(input_tokens: int, output_tokens: int, web_searches: int) -> float:
    return round(
        input_tokens / 1_000_000 * config.PRICE_INPUT_PER_MTOK
        + output_tokens / 1_000_000 * config.PRICE_OUTPUT_PER_MTOK
        + web_searches * config.PRICE_PER_WEB_SEARCH,
        5,
    )
