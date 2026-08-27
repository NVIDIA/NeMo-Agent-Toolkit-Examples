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
"""Unit tests for the clause chunker, index round-trip, search, and abstention.

All tests are offline — no NVIDIA endpoint or Hugging Face download involved.
"""
import numpy as np
import pytest

from nat_clausefinder_3gpp.corpus import chunk_markdown
from nat_clausefinder_3gpp.corpus import cosine_topk
from nat_clausefinder_3gpp.corpus import format_abstain
from nat_clausefinder_3gpp.corpus import format_hits
from nat_clausefinder_3gpp.corpus import load_index
from nat_clausefinder_3gpp.corpus import save_index

SAMPLE_MD = """\
# 3GPP TS 38.331 V18.0.0 (2023-12)

Title page text that must be dropped.

## 5 Procedures

Intro text for procedures.

### 5.3 Connection control

#### 5.3.5 RRC reconfiguration

##### 5.3.5.3 Reception of an RRCReconfiguration by the UE

The UE shall perform the following actions upon reception.

##### 5.3.5.13b SCG deactivation

The UE shall deactivate the SCG.
"""


def test_chunker_extracts_clauses_and_drops_front_matter():
    chunks = chunk_markdown(SAMPLE_MD, spec="TS 38.331", release="Rel-18")
    clauses = [c.clause for c in chunks]
    assert "5.3.5.3" in clauses
    assert "5.3.5.13b" in clauses  # letter-suffixed clause numbers parse
    assert all("Title page text" not in c.text for c in chunks)


def test_chunker_breadcrumbs_track_ancestors():
    chunks = chunk_markdown(SAMPLE_MD, spec="TS 38.331", release="Rel-18")
    leaf = next(c for c in chunks if c.clause == "5.3.5.3")
    assert leaf.breadcrumbs == ["5 Procedures", "5.3 Connection control", "5.3.5 RRC reconfiguration"]
    assert leaf.clause_title == "Reception of an RRCReconfiguration by the UE"


def test_index_roundtrip_and_search(tmp_path):
    chunks = chunk_markdown(SAMPLE_MD, spec="TS 38.331", release="Rel-18")
    rng = np.random.default_rng(0)
    embeddings = rng.normal(size=(len(chunks), 8)).astype(np.float32)
    save_index(tmp_path, chunks, embeddings)

    loaded_chunks, loaded_emb = load_index(tmp_path)
    assert len(loaded_chunks) == len(chunks)
    # stored embeddings are L2-normalized
    assert np.allclose(np.linalg.norm(loaded_emb, axis=1), 1.0, atol=1e-5)

    # query equal to a stored vector must rank that vector first with score ~1
    hits = cosine_topk(embeddings[2], loaded_emb, k=3)
    assert hits[0][0] == 2
    assert hits[0][1] == pytest.approx(1.0, abs=1e-5)


def test_load_index_rejects_length_mismatch(tmp_path):
    chunks = chunk_markdown(SAMPLE_MD, spec="TS 38.331", release="Rel-18")
    save_index(tmp_path, chunks, np.ones((len(chunks), 4), dtype=np.float32))
    # corrupt: drop one chunk line
    lines = (tmp_path / "chunks.jsonl").read_text().splitlines()
    (tmp_path / "chunks.jsonl").write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(ValueError, match="index corrupt"):
        load_index(tmp_path)


def test_format_hits_carries_citation_tags():
    chunks = [c.to_dict() for c in chunk_markdown(SAMPLE_MD, "TS 38.331", "Rel-18")]
    idx = next(i for i, c in enumerate(chunks) if c["clause"] == "5.3.5.3")
    rendered = format_hits(chunks, [(idx, 0.87)])
    assert "[TS 38.331 §5.3.5.3" in rendered
    assert "Cite every claim" in rendered


def test_format_abstain_is_explicit_and_lists_specs():
    message = format_abstain(0.21, 0.35, ["TS 38.331", "TS 23.501", "TS 38.331"])
    assert message.startswith("ABSTAIN")
    assert "0.210" in message and "0.35" in message
    assert "TS 23.501, TS 38.331" in message  # deduped, sorted
    assert "do not answer from prior knowledge" in message


def test_long_clause_is_split_not_truncated():
    long_md = "#### 5.1 Long clause\n\n" + "\n\n".join(f"Paragraph {i} " + "x" * 400 for i in range(20))
    chunks = chunk_markdown(long_md, spec="TS 38.331", release="Rel-18")
    assert len(chunks) > 1
    joined = "\n\n".join(c.text for c in chunks)
    assert all(f"Paragraph {i}" in joined for i in range(20))
    assert all(c.clause == "5.1" for c in chunks)
