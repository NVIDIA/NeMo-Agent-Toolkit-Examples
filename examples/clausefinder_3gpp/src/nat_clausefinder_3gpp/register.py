# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
"""3GPP clause search — a domain RAG tool with a calibrated abstention gate.

Registers ``threegpp_clause_search``: given a natural-language question about
the indexed 3GPP specifications, it embeds the query with an NVIDIA-hosted
embedding model, runs exact cosine search over the local clause index built by
``scripts/build_index.py``, and returns clause-tagged spec text ready for
citation — or an explicit ABSTAIN message when the best match falls below the
relevance threshold, so the agent refuses instead of guessing.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import numpy as np
from pydantic import Field

from nat.plugin_api import Builder
from nat.plugin_api import FunctionBaseConfig
from nat.plugin_api import FunctionInfo
from nat.plugin_api import register_function
from nat_clausefinder_3gpp.corpus import cosine_topk
from nat_clausefinder_3gpp.corpus import format_abstain
from nat_clausefinder_3gpp.corpus import format_hits
from nat_clausefinder_3gpp.corpus import load_index

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class ThreeGPPClauseSearchConfig(FunctionBaseConfig, name="threegpp_clause_search"):
    """Clause-cited retrieval over a local 3GPP spec index, with abstention."""
    index_dir: str = Field(default="data/index", description="Directory produced by scripts/build_index.py")
    embedding_model: str = Field(default="nvidia/nemotron-3-embed-1b",
                                 description="NVIDIA-hosted embedding model for queries "
                                 "(must match the model used at ingest)")
    top_k: int = Field(default=6, description="Clauses returned per query")
    abstain_threshold: float = Field(default=0.42,
                                     description="Cosine floor: below this the tool reports ABSTAIN instead of "
                                     "returning weak matches for the agent to over-interpret")


@register_function(config_type=ThreeGPPClauseSearchConfig)
async def threegpp_clause_search(config: ThreeGPPClauseSearchConfig, _builder: Builder):
    from openai import OpenAI  # deferred so import of this module needs no API key

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY is not set — get one free at build.nvidia.com")

    chunks, embeddings = load_index(Path(config.index_dir))
    specs = [c["spec"] for c in chunks]
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    logger.info("3GPP clause index loaded: %d chunks, %d specs", len(chunks), len(set(specs)))

    def _search(question: str) -> str:
        response = client.embeddings.create(model=config.embedding_model,
                                            input=[question],
                                            extra_body={
                                                "input_type": "query", "truncate": "END"
                                            })
        query_vec = np.asarray(response.data[0].embedding, dtype=np.float32)
        hits = cosine_topk(query_vec, embeddings, config.top_k)
        top_score = hits[0][1] if hits else 0.0
        if top_score < config.abstain_threshold:
            return format_abstain(top_score, config.abstain_threshold, specs)
        return format_hits(chunks, hits)

    async def _respond(question: str) -> str:
        """Search the indexed 3GPP specifications for clauses relevant to a
        telecom-standards question. Returns spec text tagged with citable
        clause references like [TS 38.331 §5.3.5.3] — every claim in the final
        answer must cite one of these tags. If the tool returns ABSTAIN, tell
        the user the indexed specs do not cover the question."""
        return await asyncio.to_thread(_search, question)

    yield FunctionInfo.from_fn(_respond, description=_respond.__doc__)
