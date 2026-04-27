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
"""Answer cleaning utilities for GAIA-style evaluation."""

import logging
import re

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

_ANSWER_CLEANING_PROMPT = """\
You are an answer-formatting assistant for a benchmark evaluation.

You will receive a QUESTION and a RAW ANSWER produced by an AI agent.
Your job is to extract and format ONLY the final answer so it can be \
compared to a ground-truth string.

## Rules

### Extraction
1. **Extract only the core answer** — remove preamble ("The answer is…", \
"Based on my analysis…", "Therefore…"), trailing explanation, and formatting \
artifacts (markdown bold, prefixes, etc.).
2. **Never change the substance** — do not add, remove, or alter factual \
content. "42" stays "42", not "forty-two".
3. **Preserve completeness** — if the answer is a formula like \
"(¬A → B) ↔ (A ∨ ¬B)", output it in full. Do NOT truncate.

### Formatting
4. **Match the question's expected type**:
   - Number → just the number, no units unless required.
   - Name → just the name.
   - List → use the delimiter the question specifies (default: comma-separated).
   - Sentence → capitalize first word, end with period.
   - Yes/No → Title Case ("Yes" / "No").
   - Direction → Title Case ("Left", "Right", "North", etc.).
5. **Match the question's expected scale** — if the question asks \
"how many thousand hours" and the raw answer is "17000 hours", output "17". \
Similarly, "how many million" → divide by 1,000,000.
6. **Preserve capitalization** — do NOT change case unless the question \
specifies it, or for Yes/No and directional answers.
7. **Punctuation** — do NOT add a trailing period unless a sentence is \
requested. Remove trailing periods from words, names, or numbers. Remove \
currency symbols ($, €) unless asked for.

### Output
8. **If the raw answer is empty or says it cannot answer**, output as-is.
9. **Output ONLY the cleaned answer** — no quotes, no explanation, nothing else.
"""


async def clean_answer_with_llm(
    llm,
    question: str,
    response: str,
) -> str:
    """Clean the agent response using an LLM for context-aware formatting.

    The LLM sees both the original question and the raw answer so it can
    make context-appropriate formatting decisions (e.g., stripping preamble,
    adjusting units/scale, preserving formulas).

    Falls back to returning the raw response (stripped) if the LLM call fails.

    Args:
        llm: A LangChain BaseChatModel instance.
        question: The original question that was asked.
        response: The raw agent response to clean.

    Returns:
        Cleaned answer string.
    """
    if not response or not response.strip():
        return response

    raw = response.strip()

    # Short-circuit: if the answer is already very short and simple, skip LLM
    if len(raw) <= 3 and re.fullmatch(r"-?\d+\.?\d*", raw):
        return raw

    try:
        messages = [
            SystemMessage(content=_ANSWER_CLEANING_PROMPT),
            HumanMessage(content=f"QUESTION:\n{question}\n\nRAW ANSWER:\n{raw}"),
        ]
        result = await llm.ainvoke(messages)
        cleaned = result.content.strip()

        # Guard: if the LLM returned something empty or much longer than
        # the raw answer, something went wrong — fall back to raw.
        if not cleaned:
            logger.warning("LLM answer cleaning returned empty, using raw answer")
            return raw
        if len(cleaned) > len(raw) * 2 + 50:
            logger.warning("LLM answer cleaning returned suspiciously long output, using raw answer")
            return raw

        logger.debug(f"LLM answer cleaning: {raw!r} -> {cleaned!r}")
        return cleaned

    except Exception as e:
        logger.warning(f"LLM answer cleaning failed ({e}), using raw answer")
        return raw
