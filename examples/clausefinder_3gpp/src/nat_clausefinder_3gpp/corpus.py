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
"""Clause-aware chunking and a small local vector index for 3GPP specs.

Pure helpers with no NeMo Agent Toolkit or network dependencies so they are
unit-testable and reusable from both the ingest script and the registered
function. The GSMA Open Telco markdown mirror renders each spec clause as a
markdown heading of the form ``#### 5.3.5.13b SCG deactivation`` — clause
number then title — which this module treats as the chunk boundary.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import numpy as np

# ``#### 5.3.5.13b1 Title`` -> ("####", "5.3.5.13b1", "Title")
CLAUSE_HEADING_RE = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*(?:[a-z]\d*)*)\s+(\S.*)$")

MAX_CHUNK_CHARS = 4000  # ~1000 tokens; clauses longer than this are split on paragraphs


@dataclass
class Chunk:
    spec: str  # e.g. "TS 38.331"
    release: str  # e.g. "Rel-18"
    clause: str  # e.g. "5.3.5.13"
    clause_title: str
    text: str
    breadcrumbs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spec": self.spec,
            "release": self.release,
            "clause": self.clause,
            "clause_title": self.clause_title,
            "text": self.text,
            "breadcrumbs": self.breadcrumbs
        }


def chunk_markdown(markdown: str, spec: str, release: str) -> list[Chunk]:
    """Split a GSMA-mirror spec markdown file into clause-aligned chunks.

    Text before the first clause heading (title page, table of contents) is
    dropped. Each chunk carries its clause number, title, and the breadcrumb
    trail of ancestor clause titles so retrieved text stays self-describing.
    """
    chunks: list[Chunk] = []
    current: Chunk | None = None
    # breadcrumb stack of (heading_level, "clause title") entries
    trail: list[tuple[int, str]] = []
    lines: list[str] = []

    def flush() -> None:
        nonlocal current, lines
        if current is None:
            return
        body = "\n".join(lines).strip()
        if body:
            for piece in _split_long(body):
                chunks.append(
                    Chunk(spec=current.spec,
                          release=current.release,
                          clause=current.clause,
                          clause_title=current.clause_title,
                          text=piece,
                          breadcrumbs=list(current.breadcrumbs)))
        current, lines = None, []

    for line in markdown.splitlines():
        m = CLAUSE_HEADING_RE.match(line)
        if m:
            flush()
            level, clause, title = len(m.group(1)), m.group(2), m.group(3).strip()
            while trail and trail[-1][0] >= level:
                trail.pop()
            breadcrumbs = [t for _, t in trail]
            trail.append((level, f"{clause} {title}"))
            current = Chunk(spec=spec,
                            release=release,
                            clause=clause,
                            clause_title=title,
                            text="",
                            breadcrumbs=breadcrumbs)
        elif current is not None:
            lines.append(line)
    flush()
    return chunks


def _split_long(body: str) -> list[str]:
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]
    pieces, buf = [], ""
    for para in body.split("\n\n"):
        if buf and len(buf) + len(para) + 2 > MAX_CHUNK_CHARS:
            pieces.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        pieces.append(buf)
    return pieces


# --------------------------------------------------------------------------
# Index persistence and search
# --------------------------------------------------------------------------


def save_index(index_dir: Path, chunks: list[Chunk], embeddings: np.ndarray) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    np.save(index_dir / "embeddings.npy", (embeddings / np.clip(norms, 1e-9, None)).astype(np.float32))
    with open(index_dir / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")


def load_index(index_dir: Path) -> tuple[list[dict], np.ndarray]:
    embeddings = np.load(index_dir / "embeddings.npy")
    with open(index_dir / "chunks.jsonl", encoding="utf-8") as fh:
        chunks = [json.loads(line) for line in fh if line.strip()]
    if len(chunks) != embeddings.shape[0]:
        raise ValueError(f"index corrupt: {len(chunks)} chunks vs {embeddings.shape[0]} embeddings")
    return chunks, embeddings


def cosine_topk(query_vec: np.ndarray, embeddings: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Exact cosine search (embeddings are stored L2-normalized)."""
    q = query_vec / max(float(np.linalg.norm(query_vec)), 1e-9)
    scores = embeddings @ q
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order]


def format_hits(chunks: list[dict], hits: list[tuple[int, float]]) -> str:
    """Render retrieved clauses for the agent, with citation-ready tags."""
    blocks = []
    for rank, (idx, score) in enumerate(hits, start=1):
        c = chunks[idx]
        crumb = " > ".join(c["breadcrumbs"]) if c["breadcrumbs"] else ""
        header = f"[{c['spec']} §{c['clause']} {c['clause_title']}] ({c['release']}, score={score:.3f})"
        if crumb:
            header += f"\n  context: {crumb}"
        blocks.append(f"{header}\n{c['text']}")
    guidance = ("Cite every claim with the bracketed clause reference exactly as given, "
                "e.g. [TS 38.331 §5.3.5.3]. Do not cite clauses that are not listed above.")
    return "\n\n---\n\n".join(blocks) + f"\n\n{guidance}"


def format_abstain(top_score: float, threshold: float, specs: list[str]) -> str:
    return (f"ABSTAIN: no sufficiently relevant clause found (top score {top_score:.3f} "
            f"< threshold {threshold}). Specs searched: {', '.join(sorted(set(specs)))}. "
            "Tell the user the indexed specifications do not answer this question; "
            "do not answer from prior knowledge.")
