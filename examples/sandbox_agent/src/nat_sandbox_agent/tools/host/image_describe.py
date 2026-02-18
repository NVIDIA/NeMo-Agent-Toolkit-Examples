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
"""Host-side image description tool using a vision LLM.

Reads an image from the sandbox, encodes it as base64, and sends it to
a vision-capable LLM for analysis. Runs on the host to keep API keys
out of the sandbox.
"""

import base64
import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from pydantic import Field

from nat_sandbox_agent.sandbox.base import BaseSandbox

logger = logging.getLogger(__name__)

# File extensions supported by common vision LLMs
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}

# Map extensions to MIME types
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
}


class ImageDescribeInput(BaseModel):
    """Input schema for image_describe tool."""

    image_path: str = Field(
        description="Path to the image file inside the sandbox (e.g. /workspace/input/photo.png).",
    )
    question: str = Field(
        default="Describe this image in detail.",
        description=(
            "A specific question or instruction about the image. "
            "Examples: 'What text is visible?', 'Describe the geometric shapes.', "
            "'What colors are used in this chart?'"
        ),
    )


class ImageDescribeTool:
    """Analyzes images using a vision-capable LLM.

    Data flow:
        sandbox.read_file_bytes(path) -> base64 encode -> vision_llm.ainvoke() -> text description
    """

    def __init__(self, sandbox: BaseSandbox, vision_llm: Any):
        self.sandbox = sandbox
        self.vision_llm = vision_llm

    async def describe(self, image_path: str, question: str = "Describe this image in detail.") -> dict[str, Any]:
        """Analyze an image file from the sandbox using a vision model.

        Args:
            image_path: Path to the image inside the sandbox.
            question: Question or instruction about the image.

        Returns:
            Dict with status, description, and image_path.
        """
        logger.info(f"Image describe: {image_path} | question: {question[:80]}...")

        # 1. Validate file extension
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            return {
                "status": "error",
                "error": f"Unsupported image format '{ext}'. Supported formats: {supported}",
                "image_path": image_path,
            }

        # 2. Read image bytes from sandbox
        try:
            image_bytes = await self.sandbox.read_file_bytes(image_path)
        except FileNotFoundError:
            return {
                "status": "error",
                "error": f"Image file not found: {image_path}",
                "image_path": image_path,
            }
        except Exception as e:
            logger.error(f"Failed to read image {image_path}: {e}")
            return {
                "status": "error",
                "error": f"Failed to read image file: {e}",
                "image_path": image_path,
            }

        # 3. Base64 encode and build data URI
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = MIME_TYPES.get(ext, "image/png")
        data_uri = f"data:{mime_type};base64,{b64_data}"

        # 4. Build multimodal message (LangChain standard format)
        message = HumanMessage(
            content=[
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]
        )

        # 5. Call vision LLM
        try:
            response = await self.vision_llm.ainvoke([message])
        except Exception as e:
            logger.error(f"Vision LLM call failed: {e}")
            return {
                "status": "error",
                "error": f"Vision model error: {e}",
                "image_path": image_path,
            }

        # 6. Return description
        description = response.content if hasattr(response, "content") else str(response)

        logger.info(f"Image describe returned {len(description)} chars for {image_path}")
        return {
            "status": "success",
            "description": description,
            "image_path": image_path,
        }


def create_image_describe_tool(sandbox: BaseSandbox, vision_llm: Any) -> StructuredTool:
    """Create the image_describe tool.

    Args:
        sandbox: Sandbox instance for reading image files.
        vision_llm: A vision-capable LLM (LangChain BaseChatModel).

    Returns:
        LangChain StructuredTool instance.
    """
    tool = ImageDescribeTool(sandbox, vision_llm)

    return StructuredTool.from_function(
        coroutine=tool.describe,
        name="image_describe",
        description=(
            "Analyze an image file using a vision model. "
            "Reads the image from the sandbox and returns a text description. "
            "Use this for understanding visual content: charts, diagrams, geometric shapes, "
            "screenshots, handwritten text, musical notation, photos, etc. "
            "For pixel-level processing (cropping, color extraction, OCR coordinates), "
            "use the python tool with PIL/OpenCV instead."
        ),
        args_schema=ImageDescribeInput,
    )
