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
"""Tests for host-side tools (web_search, web_fetch)."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
import pytest

from nat_sandbox_agent.tools.host.web_fetch import WebFetchInput
from nat_sandbox_agent.tools.host.web_fetch import create_web_fetch_tool
from nat_sandbox_agent.tools.host.web_fetch import web_fetch
from nat_sandbox_agent.tools.host.web_search import HostWebSearchTool
from nat_sandbox_agent.tools.host.web_search import create_web_search_tool


class TestHostWebSearchTool:
    """Tests for HostWebSearchTool."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        tool = HostWebSearchTool(api_key="test-key")

        assert tool._api_key == "test-key"
        assert tool._client is None

    def test_init_uses_env_var(self, monkeypatch):
        """Test that API key is read from environment."""
        monkeypatch.setenv("TAVILY_API_KEY", "env-api-key")
        tool = HostWebSearchTool()

        assert tool._api_key == "env-api-key"

    def test_get_client_raises_without_api_key(self):
        """Test that getting client without API key raises error."""
        tool = HostWebSearchTool(api_key=None)
        tool._api_key = None  # Ensure no key

        with pytest.raises(ValueError, match="TAVILY_API_KEY not set"):
            tool._get_client()

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful web search."""
        tool = HostWebSearchTool(api_key="test-key")

        mock_client = MagicMock()
        mock_client.search = AsyncMock(
            return_value={
                "results": [{
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "This is a test snippet",
                    "score": 0.95,
                }],
                "answer": "The answer is 42",
            })
        tool._client = mock_client

        result = await tool.search("test query", num_results=5)

        assert result["status"] == "success"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Test Result"
        assert result["results"][0]["url"] == "https://example.com"
        assert result["results"][0]["snippet"] == "This is a test snippet"
        assert result["answer"] == "The answer is 42"

        mock_client.search.assert_called_once_with(
            query="test query",
            max_results=5,
            include_answer=True,
        )

    @pytest.mark.asyncio
    async def test_search_limits_max_results(self):
        """Test that max_results is capped at 10."""
        tool = HostWebSearchTool(api_key="test-key")

        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value={"results": [], "answer": None})
        tool._client = mock_client

        await tool.search("test", num_results=15)

        mock_client.search.assert_called_once_with(
            query="test",
            max_results=10,  # Should be capped
            include_answer=True,
        )

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test error handling in search."""
        tool = HostWebSearchTool(api_key="test-key")

        mock_client = MagicMock()
        mock_client.search = AsyncMock(side_effect=Exception("API error"))
        tool._client = mock_client

        result = await tool.search("test query")

        assert result["status"] == "error"
        assert "API error" in result["error"]


class TestCreateWebSearchTool:
    """Tests for create_web_search_tool function."""

    def test_creates_structured_tool(self):
        """Test that function creates a StructuredTool."""
        tool = create_web_search_tool(api_key="test-key")

        assert tool.name == "web_search"
        assert "Search the web" in tool.description

    def test_tool_has_correct_schema(self):
        """Test that tool has correct input schema."""
        tool = create_web_search_tool(api_key="test-key")

        # Check that the tool has expected input fields
        schema = tool.args_schema.schema()
        assert "query" in schema["properties"]
        assert "num_results" in schema["properties"]


# ============ Web Fetch Tests ============


def _mock_response(text, content_type="text/html", status_code=200, url="https://example.com"):
    """Helper to create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.status_code = status_code
    resp.url = url
    resp.headers = {"content-type": content_type}
    resp.raise_for_status = MagicMock()
    return resp


class TestWebFetchInput:
    """Tests for WebFetchInput schema validation."""

    def test_defaults(self):
        """Test default values."""
        inp = WebFetchInput(url="https://example.com")
        assert inp.url == "https://example.com"
        assert inp.max_length == 5000
        assert inp.start_index == 0
        assert inp.raw is False

    def test_max_length_bounds(self):
        """Test that max_length enforces bounds."""
        with pytest.raises(Exception):
            WebFetchInput(url="https://example.com", max_length=0)
        with pytest.raises(Exception):
            WebFetchInput(url="https://example.com", max_length=200000)

    def test_start_index_non_negative(self):
        """Test that start_index must be non-negative."""
        with pytest.raises(Exception):
            WebFetchInput(url="https://example.com", start_index=-1)


class TestWebFetch:
    """Tests for the web_fetch async function."""

    @pytest.mark.asyncio
    async def test_html_to_markdown(self):
        """Test that HTML content is converted to Markdown."""
        html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
        mock_resp = _mock_response(html, "text/html")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://example.com")

        assert result["status"] == "success"
        assert "Title" in result["content"]
        assert "Hello world" in result["content"]
        assert result["total_length"] > 0

    @pytest.mark.asyncio
    async def test_plain_text_passthrough(self):
        """Test that plain text is returned without conversion."""
        text = "Just plain text content"
        mock_resp = _mock_response(text, "text/plain")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://example.com/file.txt")

        assert result["status"] == "success"
        assert result["content"] == text

    @pytest.mark.asyncio
    async def test_json_passthrough(self):
        """Test that JSON is returned without conversion."""
        json_text = '{"key": "value"}'
        mock_resp = _mock_response(json_text, "application/json")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://api.example.com/data")

        assert result["status"] == "success"
        assert result["content"] == json_text

    @pytest.mark.asyncio
    async def test_raw_mode_skips_conversion(self):
        """Test that raw=True returns content without HTML-to-Markdown."""
        html = "<h1>Title</h1>"
        mock_resp = _mock_response(html, "text/html")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://example.com", raw=True)

        assert result["status"] == "success"
        assert "<h1>" in result["content"]

    @pytest.mark.asyncio
    async def test_pagination(self):
        """Test start_index and max_length pagination."""
        # Content = "AAAA...BBBB..." (20 A's + 20 B's = 40 chars)
        text = "A" * 20 + "B" * 20
        mock_resp = _mock_response(text, "text/plain")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            # First page
            result = await web_fetch("https://example.com", max_length=20, start_index=0)

        assert result["content"] == "A" * 20
        assert result["total_length"] == 40
        assert result["has_more"] is True
        assert result["next_start_index"] == 20

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            # Second page
            result2 = await web_fetch("https://example.com", max_length=20, start_index=20)

        assert result2["content"] == "B" * 20
        assert "has_more" not in result2

    @pytest.mark.asyncio
    async def test_http_error(self):
        """Test handling of HTTP errors."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_resp.reason_phrase = "Not Found"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Not Found",
                                                                       request=MagicMock(),
                                                                       response=mock_resp)

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://example.com/missing")

        assert result["status"] == "error"
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test handling of timeout."""
        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.side_effect = httpx.TimeoutException("timed out")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://slow.example.com")

        assert result["status"] == "error"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_converts_html_headings_to_markdown(self):
        """Test that HTML headings are converted to ATX-style Markdown."""
        html = "<html><body><h1>Title</h1><h2>Subtitle</h2><p>Body text</p></body></html>"
        mock_resp = _mock_response(html, "text/html")

        with patch("nat_sandbox_agent.tools.host.web_fetch.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await web_fetch("https://example.com")

        content = result["content"]
        # ATX headings: # Title, ## Subtitle
        assert "# Title" in content
        assert "## Subtitle" in content
        assert "Body text" in content
        # HTML tags should not appear in output
        assert "<h1>" not in content
        assert "<p>" not in content


class TestCreateWebFetchTool:
    """Tests for create_web_fetch_tool function."""

    def test_creates_structured_tool(self):
        """Test that function creates a StructuredTool."""
        tool = create_web_fetch_tool()

        assert tool.name == "web_fetch"
        assert "Markdown" in tool.description

    def test_tool_has_correct_schema(self):
        """Test that tool has correct input schema."""
        tool = create_web_fetch_tool()

        schema = tool.args_schema.model_json_schema()
        assert "url" in schema["properties"]
        assert "max_length" in schema["properties"]
        assert "start_index" in schema["properties"]
        assert "raw" in schema["properties"]

    def test_accepts_custom_max_output_chars(self):
        """Test that max_output_chars parameter is accepted."""
        tool = create_web_fetch_tool(max_output_chars=5000)
        assert tool is not None
