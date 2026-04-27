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
"""Tests for utility functions."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from nat_sandbox_agent.utils.answer_cleaning import clean_answer_with_llm


class TestCleanAnswerWithLLM:
    """Tests for the async LLM-based answer cleaning function."""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Test that empty/None input is returned as-is without calling LLM."""
        llm = AsyncMock()
        assert await clean_answer_with_llm(llm, "question", "") == ""
        assert await clean_answer_with_llm(llm, "question", None) is None
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_number_skips_llm(self):
        """Test that short numeric answers skip the LLM call."""
        llm = AsyncMock()
        assert await clean_answer_with_llm(llm, "How many?", "42") == "42"
        assert await clean_answer_with_llm(llm, "How many?", "-5") == "-5"
        assert await clean_answer_with_llm(llm, "What is pi?", "3.1") == "3.1"
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_called_with_question_and_answer(self):
        """Test that LLM is called with both question and raw answer."""
        mock_result = MagicMock()
        mock_result.content = "Paris"
        llm = AsyncMock()
        llm.ainvoke.return_value = mock_result

        result = await clean_answer_with_llm(llm, "What is the capital of France?", "The answer is Paris")
        assert result == "Paris"

        # Verify LLM was called with the right messages
        call_args = llm.ainvoke.call_args[0][0]
        assert len(call_args) == 2
        assert "QUESTION:" in call_args[1].content
        assert "capital of France" in call_args[1].content
        assert "RAW ANSWER:" in call_args[1].content
        assert "The answer is Paris" in call_args[1].content

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self):
        """Test that raw answer is returned when LLM call fails."""
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("API error")

        result = await clean_answer_with_llm(llm, "question", "  The answer is 42  ")
        assert result == "The answer is 42"

    @pytest.mark.asyncio
    async def test_fallback_on_empty_llm_response(self):
        """Test that raw answer is returned when LLM returns empty."""
        mock_result = MagicMock()
        mock_result.content = ""
        llm = AsyncMock()
        llm.ainvoke.return_value = mock_result

        result = await clean_answer_with_llm(llm, "question", "The answer is 42")
        assert result == "The answer is 42"

    @pytest.mark.asyncio
    async def test_fallback_on_overlong_llm_response(self):
        """Test that raw answer is returned when LLM output is suspiciously long."""
        mock_result = MagicMock()
        mock_result.content = "A" * 500  # Much longer than raw answer
        llm = AsyncMock()
        llm.ainvoke.return_value = mock_result

        result = await clean_answer_with_llm(llm, "question", "42")
        assert result == "42"

    @pytest.mark.asyncio
    async def test_preserves_formula(self):
        """Test that LLM-cleaned formulas are preserved."""
        formula = "(¬A → B) ↔ (A ∨ ¬B)"
        mock_result = MagicMock()
        mock_result.content = formula
        llm = AsyncMock()
        llm.ainvoke.return_value = mock_result

        result = await clean_answer_with_llm(llm, "What is the full logical equivalence?", f"The formula is {formula}")
        assert result == formula
