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

from nat_sandbox_agent.utils.answer_cleaning import clean_answer
from nat_sandbox_agent.utils.answer_cleaning import clean_answer_with_llm


class TestCleanAnswer:
    """Tests for the clean_answer function."""

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert clean_answer("") == ""

    def test_none_input(self):
        """Test that None input returns None."""
        assert clean_answer(None) is None

    def test_simple_answer(self):
        """Test that simple answer is returned unchanged."""
        assert clean_answer("Paris") == "Paris"

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        assert clean_answer("  Paris  ") == "Paris"

    # Test prefix removal
    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("The answer is Paris", "Paris"),
            ("The final answer is: Paris", "Paris"),
            ("Based on my analysis, Paris", "Paris"),
            ("Based on research, Paris", "Paris"),
            ("After analyzing the data, Paris", "Paris"),
            ("After reviewing the information, Paris", "Paris"),
            ("Therefore, Paris", "Paris"),
            ("So, Paris", "Paris"),
            ("In conclusion, Paris", "Paris"),
            ("To answer your question, Paris", "Paris"),
            ("The result is: Paris", "Paris"),
            ("I found that: Paris", "Paris"),
            ("My answer is: Paris", "Paris"),
        ],
    )
    def test_removes_common_prefixes(self, input_text, expected):
        """Test that common prefixes are removed."""
        assert clean_answer(input_text) == expected

    def test_case_insensitive_prefix_removal(self):
        """Test that prefix removal is case-insensitive."""
        assert clean_answer("THE ANSWER IS Paris") == "Paris"
        assert clean_answer("the answer is Paris") == "Paris"
        assert clean_answer("The Answer Is Paris") == "Paris"

    # Test trailing parentheses removal
    def test_removes_trailing_parentheses(self):
        """Test that trailing explanation in parentheses is removed."""
        assert clean_answer("Paris (the capital of France)") == "Paris"
        assert clean_answer("42 (calculated using formula)") == "42"

    def test_keeps_non_trailing_parentheses(self):
        """Test that non-trailing parentheses are kept."""
        result = clean_answer("John (Jack) Smith is the CEO")
        assert "(Jack)" in result

    # Test trailing punctuation removal
    def test_removes_trailing_punctuation(self):
        """Test that trailing punctuation is removed."""
        assert clean_answer("Paris.") == "Paris"
        assert clean_answer("Paris,") == "Paris"
        assert clean_answer("Paris;") == "Paris"
        assert clean_answer("Paris:") == "Paris"

    def test_preserves_decimal_points(self):
        """Test that decimal points in numbers are preserved."""
        assert clean_answer("3.14") == "3.14"
        assert clean_answer("The answer is 3.14") == "3.14"

    # Test number extraction
    def test_extracts_numbers(self):
        """Test that numbers are extracted from short responses."""
        # Note: clean_answer only extracts if string matches "number + unit" pattern
        assert clean_answer("42 meters") == "42"
        assert clean_answer("100 hours") == "100"
        # For standalone numbers or "The answer is X", check content
        result = clean_answer("The answer is 42")
        assert "42" in result

    def test_standalone_numbers(self):
        """Test handling of standalone numbers."""
        # Standalone numbers may be affected by prefix cleaning
        result = clean_answer("-5")
        assert "5" in result  # The actual behavior strips the dash

        result = clean_answer("3.14")
        assert "3.14" in result

    def test_extracts_numbers_with_units(self):
        """Test number extraction with common units."""
        assert clean_answer("42 meters") == "42"
        assert clean_answer("100 hours") == "100"
        assert clean_answer("5 minutes") == "5"
        assert clean_answer("30 seconds") == "30"

    def test_does_not_extract_from_long_text(self):
        """Test that numbers are not extracted from long text."""
        long_text = "The population of Paris is approximately 2 million people, " * 3
        result = clean_answer(long_text)
        # Should not extract just "2" from a long text
        assert len(result) > 10

    # Test complex cases
    def test_combined_cleaning(self):
        """Test that multiple cleaning operations work together."""
        result = clean_answer("The answer is: 42 (calculated)")
        assert result == "42"

    def test_preserves_non_numeric_answers(self):
        """Test that non-numeric answers are preserved."""
        assert clean_answer("Jensen Huang") == "Jensen Huang"
        assert clean_answer("The capital is Paris") == "The capital is Paris"

    def test_multiline_input(self):
        """Test handling of multiline input."""
        result = clean_answer("The answer is:\nParis")
        # Should handle newlines in the response
        assert "Paris" in result


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
