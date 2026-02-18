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
"""Tests for system prompts."""

from nat_sandbox_agent.prompts import SANDBOX_AGENT_SYSTEM_PROMPT
from nat_sandbox_agent.prompts import get_system_prompt


class TestSystemPromptV1:
    """Tests for v1 system prompt generation."""

    def test_default_prompt_exists(self):
        """Test that default system prompt is defined."""
        assert SANDBOX_AGENT_SYSTEM_PROMPT is not None
        assert len(SANDBOX_AGENT_SYSTEM_PROMPT) > 0

    def test_default_prompt_contains_capabilities(self):
        """Test that default prompt describes capabilities."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT

        assert "shell" in prompt.lower()
        assert "python" in prompt.lower()
        assert "file" in prompt.lower()
        assert "web" in prompt.lower()

    def test_prompt_contains_print_guidance(self):
        """Test that prompt includes critical Python print() guidance."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "print()" in prompt
        assert "ALWAYS use print()" in prompt or "ALWAYS use `print()`" in prompt
        assert "Variables do NOT persist" in prompt
        assert "empty stdout" in prompt

    def test_prompt_contains_file_extension_mapping(self):
        """Test that prompt includes file extension to tool mapping."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert ".xlsx" in prompt
        assert ".pdf" in prompt
        assert "pdfplumber" in prompt
        assert ".mp3" in prompt
        assert "faster_whisper" in prompt
        assert ".pptx" in prompt
        assert "python-pptx" in prompt

    def test_prompt_contains_image_describe_tool(self):
        """Test that prompt includes image_describe tool description."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "image_describe" in prompt
        assert "vision model" in prompt.lower() or "vision" in prompt.lower()

    def test_prompt_contains_format_verification(self):
        """Test that prompt includes format verification checklist."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "Format Verification" in prompt
        assert "Number Format" in prompt
        assert "Unit Requirements" in prompt
        assert "Multiple Answers" in prompt
        assert "Case Sensitivity" in prompt
        assert "Date/Time Formats" in prompt

    def test_prompt_contains_package_install_guidance(self):
        """Test that prompt includes package installation guidance with root privileges."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "pip install" in prompt
        assert "apt-get install" in prompt
        assert "root privileges" in prompt

    def test_prompt_contains_calculation_verification(self):
        """Test that prompt includes calculation and reasoning verification rules."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "Calculation and Reasoning Verification" in prompt
        assert "show your work" in prompt.lower() or "step by step" in prompt.lower()

    def test_prompt_contains_data_extraction_practices(self):
        """Test that prompt includes data extraction best practices."""
        prompt = SANDBOX_AGENT_SYSTEM_PROMPT
        assert "Data Extraction Best Practices" in prompt
        assert "column headers" in prompt.lower()
        assert "row alignment" in prompt.lower()

    def test_get_prompt_with_additional_instructions(self):
        """Test getting prompt with additional instructions."""
        additional = "Always respond in JSON format."
        prompt = get_system_prompt(additional_instructions=additional)

        assert SANDBOX_AGENT_SYSTEM_PROMPT in prompt
        assert additional in prompt
