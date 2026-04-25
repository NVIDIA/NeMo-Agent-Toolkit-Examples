# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Host-side web fetch tool - lightweight HTTP content fetcher.

Fetches a URL via HTTP and converts HTML to clean Markdown.
Much faster and lighter than browser-based browsing (Playwright).

Inspired by mcp-server-fetch (https://pypi.org/project/mcp-server-fetch/).
"""

import logging
from typing import Any

import httpx
import markdownify
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from pydantic import Field

from nat_sandbox_agent.tools.common import DEFAULT_MAX_OUTPUT_CHARS

logger = logging.getLogger(__name__)

# Default user agent for fetch requests
DEFAULT_USER_AGENT = ("Mozilla/5.0 (compatible; NATSandboxAgent/1.0; +https://github.com/NVIDIA/NeMo-Agent-Toolkit)")

# Default max content length (characters) returned per call
DEFAULT_MAX_LENGTH = 5000


class WebFetchInput(BaseModel):
    """Input schema for web fetch."""

    url: str = Field(description="The URL to fetch content from.")
    max_length: int = Field(
        default=DEFAULT_MAX_LENGTH,
        description="Maximum number of characters to return. Default is 5000.",
        ge=1,
        le=100000,
    )
    start_index: int = Field(
        default=0,
        description=("Character position to start reading from. "
                     "Use this to paginate through long pages. Default is 0."),
        ge=0,
    )
    raw: bool = Field(
        default=False,
        description="If true, return raw content without HTML-to-Markdown conversion.",
    )


async def web_fetch(
    url: str,
    max_length: int = DEFAULT_MAX_LENGTH,
    start_index: int = 0,
    raw: bool = False,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> dict[str, Any]:
    """Fetch a URL and convert HTML content to Markdown.

    This is a lightweight alternative to web_browse (Playwright). It performs
    a simple HTTP GET request and converts HTML to clean Markdown text.
    Much faster but does not render JavaScript.

    Args:
        url: The URL to fetch.
        max_length: Maximum characters to return.
        start_index: Character position to start from (for pagination).
        raw: If True, return raw content without conversion.
        max_output_chars: Hard limit on output size.

    Returns:
        Dict with status, url, content, and pagination info.
    """
    logger.info(f"Web fetch: {url} (start={start_index}, max_len={max_length})")

    try:
        async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if raw or "text/plain" in content_type:
            # Return raw text content
            content = response.text
        elif "text/html" in content_type or "application/xhtml" in content_type:
            # Convert HTML to Markdown
            content = markdownify.markdownify(
                response.text,
                heading_style="ATX",
                strip=["script", "style", "nav", "footer", "header"],
            )
            # Clean up excessive whitespace
            lines = content.split("\n")
            cleaned_lines = []
            blank_count = 0
            for line in lines:
                stripped = line.rstrip()
                if not stripped:
                    blank_count += 1
                    if blank_count <= 2:
                        cleaned_lines.append("")
                else:
                    blank_count = 0
                    cleaned_lines.append(stripped)
            content = "\n".join(cleaned_lines).strip()
        elif "application/json" in content_type:
            content = response.text
        else:
            content = response.text

        # Apply pagination
        total_length = len(content)
        content = content[start_index:start_index + max_length]

        # Enforce hard limit
        if len(content) > max_output_chars:
            content = content[:max_output_chars]

        result = {
            "status": "success",
            "url": str(response.url),
            "content": content,
            "total_length": total_length,
            "start_index": start_index,
            "returned_length": len(content),
        }

        # Add pagination hint if there's more content
        if start_index + max_length < total_length:
            result["has_more"] = True
            result["next_start_index"] = start_index + max_length
            result["remaining"] = total_length - (start_index + max_length)

        logger.info(f"Web fetch returned {len(content)} chars "
                    f"(total={total_length}, start={start_index})")
        return result

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
        return {
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            "url": url,
        }
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
        return {
            "status": "error",
            "error": "Request timed out after 30 seconds",
            "url": url,
        }
    except Exception as e:
        logger.exception(f"Error fetching {url}")
        return {
            "status": "error",
            "error": str(e),
            "url": url,
        }


def create_web_fetch_tool(max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS, ) -> StructuredTool:
    """Create the web fetch tool.

    Args:
        max_output_chars: Maximum characters for tool output.

    Returns:
        LangChain StructuredTool instance.
    """
    return StructuredTool.from_function(
        coroutine=lambda url, max_length=DEFAULT_MAX_LENGTH, start_index=0, raw=False: web_fetch(
            url, max_length, start_index, raw, max_output_chars),
        name="web_fetch",
        description=("Fetch a webpage and convert it to clean Markdown text. "
                     "Much faster than web_browse but does NOT render JavaScript. "
                     "Use this for static pages, articles, documentation, and API responses. "
                     "Use 'start_index' to paginate through long content. "
                     "Tip: also works with JSON APIs — useful URLs include: "
                     "Wikipedia edit history: https://en.wikipedia.org/w/api.php?action=query"
                     "&titles=TITLE&prop=revisions&rvlimit=50&rvprop=timestamp|comment|user&format=json ; "
                     "GitHub issue events: https://api.github.com/repos/OWNER/REPO/issues/NUM/events ; "
                     "GitHub issue timeline: https://api.github.com/repos/OWNER/REPO/issues/NUM/timeline ; "
                     "arXiv monthly listings: https://arxiv.org/list/CATEGORY/YYMM"),
        args_schema=WebFetchInput,
    )
