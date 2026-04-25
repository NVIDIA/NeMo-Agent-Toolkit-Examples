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
"""Tests for host-side image_describe tool."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from nat_sandbox_agent.tools.host.image_describe import ImageDescribeTool
from nat_sandbox_agent.tools.host.image_describe import create_image_describe_tool


@pytest.fixture
def mock_vision_llm():
    """Create a mock vision LLM."""
    llm = MagicMock()
    response = MagicMock()
    response.content = "A red circle on a white background."
    llm.ainvoke = AsyncMock(return_value=response)
    return llm


@pytest.fixture
def image_tool(mock_sandbox, mock_vision_llm):
    """Create an ImageDescribeTool with mocked dependencies."""
    return ImageDescribeTool(sandbox=mock_sandbox, vision_llm=mock_vision_llm)


class TestImageDescribeTool:
    """Tests for ImageDescribeTool."""

    @pytest.mark.asyncio
    async def test_describe_success(self, image_tool, mock_sandbox, mock_vision_llm):
        """Test successful image description."""
        mock_sandbox.read_file_bytes = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n fake image data")

        result = await image_tool.describe("/workspace/input/test.png", "What is in this image?")

        assert result["status"] == "success"
        assert result["description"] == "A red circle on a white background."
        assert result["image_path"] == "/workspace/input/test.png"

        # Verify sandbox was called to read the file
        mock_sandbox.read_file_bytes.assert_called_once_with("/workspace/input/test.png")

        # Verify vision LLM was called
        mock_vision_llm.ainvoke.assert_called_once()
        call_args = mock_vision_llm.ainvoke.call_args[0][0]
        assert len(call_args) == 1  # Single HumanMessage
        message = call_args[0]
        assert len(message.content) == 2  # text + image_url
        assert message.content[0]["type"] == "text"
        assert message.content[0]["text"] == "What is in this image?"
        assert message.content[1]["type"] == "image_url"
        assert message.content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_describe_default_question(self, image_tool, mock_sandbox):
        """Test that default question is used when none provided."""
        mock_sandbox.read_file_bytes = AsyncMock(return_value=b"fake image data")

        result = await image_tool.describe("/workspace/input/photo.jpg")

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_describe_jpeg_mime_type(self, image_tool, mock_sandbox, mock_vision_llm):
        """Test that JPEG files use correct MIME type."""
        mock_sandbox.read_file_bytes = AsyncMock(return_value=b"fake jpeg data")

        await image_tool.describe("/workspace/input/photo.jpg")

        call_args = mock_vision_llm.ainvoke.call_args[0][0]
        image_url = call_args[0].content[1]["image_url"]["url"]
        assert image_url.startswith("data:image/jpeg;base64,")

    @pytest.mark.asyncio
    async def test_describe_unsupported_extension(self, image_tool):
        """Test that unsupported file extensions return error."""
        result = await image_tool.describe("/workspace/input/document.pdf")

        assert result["status"] == "error"
        assert "Unsupported image format" in result["error"]
        assert "'.pdf'" in result["error"]
        assert result["image_path"] == "/workspace/input/document.pdf"

    @pytest.mark.asyncio
    async def test_describe_xlsx_unsupported(self, image_tool):
        """Test that .xlsx extension returns error."""
        result = await image_tool.describe("/workspace/input/data.xlsx")

        assert result["status"] == "error"
        assert "Unsupported image format" in result["error"]

    @pytest.mark.asyncio
    async def test_describe_file_not_found(self, image_tool, mock_sandbox):
        """Test handling when image file does not exist."""
        mock_sandbox.read_file_bytes = AsyncMock(
            side_effect=FileNotFoundError("File not found: /workspace/input/missing.png"))

        result = await image_tool.describe("/workspace/input/missing.png")

        assert result["status"] == "error"
        assert "not found" in result["error"].lower()
        assert result["image_path"] == "/workspace/input/missing.png"

    @pytest.mark.asyncio
    async def test_describe_sandbox_read_error(self, image_tool, mock_sandbox):
        """Test handling when sandbox read fails."""
        mock_sandbox.read_file_bytes = AsyncMock(side_effect=RuntimeError("Sandbox not started"))

        result = await image_tool.describe("/workspace/input/test.png")

        assert result["status"] == "error"
        assert "Failed to read image file" in result["error"]

    @pytest.mark.asyncio
    async def test_describe_vision_llm_error(self, image_tool, mock_sandbox, mock_vision_llm):
        """Test handling when vision LLM call fails."""
        mock_sandbox.read_file_bytes = AsyncMock(return_value=b"fake image data")
        mock_vision_llm.ainvoke = AsyncMock(side_effect=Exception("API rate limit exceeded"))

        result = await image_tool.describe("/workspace/input/test.png")

        assert result["status"] == "error"
        assert "Vision model error" in result["error"]
        assert "rate limit" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_describe_all_supported_extensions(self, image_tool, mock_sandbox):
        """Test that all documented extensions are supported."""
        mock_sandbox.read_file_bytes = AsyncMock(return_value=b"fake image data")

        supported = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"]
        for ext in supported:
            result = await image_tool.describe(f"/workspace/input/test{ext}")
            assert result["status"] == "success", f"Extension {ext} should be supported"


class TestCreateImageDescribeTool:
    """Tests for create_image_describe_tool factory function."""

    def test_creates_structured_tool(self, mock_sandbox, mock_vision_llm):
        """Test that function creates a StructuredTool."""
        tool = create_image_describe_tool(mock_sandbox, mock_vision_llm)

        assert tool.name == "image_describe"
        assert "vision" in tool.description.lower()

    def test_tool_has_correct_schema(self, mock_sandbox, mock_vision_llm):
        """Test that tool has correct input schema."""
        tool = create_image_describe_tool(mock_sandbox, mock_vision_llm)

        schema = tool.args_schema.model_json_schema()
        assert "image_path" in schema["properties"]
        assert "question" in schema["properties"]

    def test_tool_is_async(self, mock_sandbox, mock_vision_llm):
        """Test that tool has an async coroutine."""
        tool = create_image_describe_tool(mock_sandbox, mock_vision_llm)

        assert tool.coroutine is not None
