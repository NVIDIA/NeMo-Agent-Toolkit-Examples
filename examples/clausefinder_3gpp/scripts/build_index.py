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
"""Build a small clause-aware 3GPP index from the GSMA Open Telco corpus.

Downloads the markdown mirror of the requested specs from the public
``GSMA/3GPP`` Hugging Face dataset (text only, images skipped), chunks them at
clause boundaries, embeds the chunks with an NVIDIA-hosted embedding model,
and writes ``embeddings.npy`` + ``chunks.jsonl`` to the index directory.

Usage (from the example root):

    export NVIDIA_API_KEY=nvapi-...
    python scripts/build_index.py --specs 38331 38300 23501 --release Rel-18

Roughly 8k chunks for the default three specs; embedding takes a few minutes
against the hosted endpoint. Ingest fails loudly if any requested spec yields
zero chunks — a corpus that silently loses documents looks identical to a
complete one in every demo, which is the failure mode this example exists to
prevent.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_ROOT / "src"))

from nat_clausefinder_3gpp.corpus import Chunk  # noqa: E402
from nat_clausefinder_3gpp.corpus import chunk_markdown  # noqa: E402
from nat_clausefinder_3gpp.corpus import save_index  # noqa: E402

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
EMBED_BATCH = 32


def spec_label(spec_dir: str) -> str:
    """``38331`` -> ``TS 38.331``; ``38101-2`` -> ``TS 38.101-2``."""
    base, _, part = spec_dir.partition("-")
    label = f"{base[:2]}.{base[2:]}"
    return f"TS {label}-{part}" if part else f"TS {label}"


def download_specs(specs: list[str], release: str, cache_dir: Path) -> dict[str, Path]:
    from huggingface_hub import snapshot_download
    patterns = [f"marked/{release}/{s[:2]}_series/{s}/*.md" for s in specs]
    root = Path(
        snapshot_download(repo_id="GSMA/3GPP", repo_type="dataset", allow_patterns=patterns, cache_dir=str(cache_dir)))
    found = {}
    for s in specs:
        md = list((root / "marked" / release / f"{s[:2]}_series" / s).glob("*.md"))
        if md:
            found[s] = md[0]
    return found


def embed_chunks(chunks: list[Chunk], model: str) -> np.ndarray:
    from openai import OpenAI
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start:start + EMBED_BATCH]
        texts = [f"{c.spec} {c.clause} {c.clause_title}\n{c.text}" for c in batch]
        response = client.embeddings.create(model=model,
                                            input=texts,
                                            extra_body={
                                                "input_type": "passage", "truncate": "END"
                                            })
        vectors.extend(d.embedding for d in response.data)
        done = min(start + EMBED_BATCH, len(chunks))
        print(f"\rembedded {done}/{len(chunks)}", end="", flush=True)
    print()
    return np.asarray(vectors, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs",
                        nargs="+",
                        default=["38331", "38300", "23501"],
                        help="spec directory names in the GSMA/3GPP dataset, e.g. 38331")
    parser.add_argument("--release", default="Rel-18")
    parser.add_argument("--index-dir", default=str(EXAMPLE_ROOT / "data" / "index"))
    parser.add_argument("--embedding-model", default="nvidia/nemotron-3-embed-1b")
    args = parser.parse_args()

    if not os.environ.get("NVIDIA_API_KEY"):
        raise SystemExit("NVIDIA_API_KEY is not set — get one free at build.nvidia.com")

    files = download_specs(args.specs, args.release, EXAMPLE_ROOT / "data" / "hf-cache")
    missing = [s for s in args.specs if s not in files]
    if missing:
        raise SystemExit(f"no markdown found for specs {missing} under {args.release} — "
                         "check the spec directory names against the GSMA/3GPP dataset")

    all_chunks: list[Chunk] = []
    for spec_dir, path in files.items():
        chunks = chunk_markdown(path.read_text(encoding="utf-8"), spec=spec_label(spec_dir), release=args.release)
        if not chunks:
            raise SystemExit(f"spec {spec_dir} produced zero chunks — refusing to "
                             "build a silently incomplete index")
        print(f"{spec_label(spec_dir)}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    embeddings = embed_chunks(all_chunks, args.embedding_model)
    save_index(Path(args.index_dir), all_chunks, embeddings)
    print(f"index written: {len(all_chunks)} chunks -> {args.index_dir}")


if __name__ == "__main__":
    main()
