<!--
SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# 3GPP ClauseFinder — clause-cited spec Q&A with an abstention gate

A telecom-domain RAG example: a ReAct agent answers questions about 3GPP
specifications with **exact clause citations** (`[TS 38.331 §5.3.5.3]`), and
**refuses to answer** when the indexed corpus does not cover the question —
instead of letting the LLM guess from prior knowledge.

The corpus is the official [GSMA Open Telco](https://huggingface.co/GSMA)
markdown mirror of the 3GPP specifications. The example indexes three
specs by default (TS 38.331 NR RRC, TS 38.300 NR overall description,
TS 23.501 5G system architecture — about 3,400 clause-aligned chunks), and
scales to any spec in the dataset by changing one command-line argument.

This example is a minimal, self-contained distillation of
[ClauseFinder](https://github.com/chinthave657/clausefinder), an open-source
3GPP assistant built on the NeMo Agent Toolkit with hybrid retrieval,
deterministic citation validation, release diffing, and NeMo Guardrails.

## Key Features

- **Clause-aware chunking**: the GSMA mirror renders every spec clause as a
  markdown heading (`#### 5.3.5.13b SCG deactivation`); chunks align to clause
  boundaries and carry breadcrumb trails of ancestor clauses, so retrieved
  text stays self-describing.
- **Calibrated abstention**: the retrieval tool returns an explicit `ABSTAIN`
  message when the top cosine score falls below a threshold, and the agent is
  instructed to relay the refusal. The default (0.42) was calibrated against
  this index: in-corpus questions score ≥ 0.50, out-of-domain questions
  ≤ 0.36.
- **All-NVIDIA endpoints**: `nvidia/nemotron-3-embed-1b` for embeddings and
  `nvidia/nemotron-3-nano-30b-a3b` for the agent, both via the free
  [build.nvidia.com](https://build.nvidia.com) API — no local GPU required.
- **Native tool calling**: the ReAct agent runs with
  `use_native_tool_calling: true`, which is markedly more reliable with
  reasoning models than parsing ReAct-formatted text.

## Installation and Setup

From the repository root:

```bash
uv pip install -e examples/clausefinder_3gpp
```

Set your NVIDIA API key (free at [build.nvidia.com](https://build.nvidia.com)):

```bash
export NVIDIA_API_KEY=nvapi-...
```

Build the index (downloads spec markdown from the public `GSMA/3GPP` dataset,
chunks it, and embeds ~3,400 chunks — a few minutes against the hosted
endpoint):

```bash
cd examples/clausefinder_3gpp
python scripts/build_index.py --specs 38331 38300 23501 --release Rel-18
```

Index other specs by passing their directory names from the
[GSMA/3GPP dataset](https://huggingface.co/datasets/GSMA/3GPP)
(e.g. `--specs 38321 38323` for MAC and PDCP).

## Running the Example

```bash
nat run --config_file configs/config.yml \
    --input "What actions does the UE take when timer T310 expires?"
```

## Expected Results

An in-corpus question returns a clause-cited answer:

```
Workflow Result:
The UE's behavior when timer T310 expires is defined in [TS 38.331 §7.1.1
Timers (Informative)]. If the timer is kept in the MCG and AS security is not
activated, the UE proceeds to RRC_IDLE; otherwise it initiates the MCG
failure-information procedure (as specified in 5.7.3b) or the connection
re-establishment procedure (as specified in 5.3.7) ... [TS 38.331 §7.1.1]
```

An out-of-corpus question abstains instead of hallucinating:

```bash
nat run --config_file configs/config.yml \
    --input "What is the maximum output power of a Bluetooth Class 1 device?"
```

```
Workflow Result:
The indexed specifications do not cover this question.
```

## Known Limitations

- The abstention gate is a semantic-similarity floor, so it cannot separate
  questions about *unindexed but similar* specs: a question about the LTE RRC
  spec (TS 36.331) scores nearly as high against NR RRC text as a genuine NR
  question does, and will be answered from NR clauses. Distinguishing
  same-family specs needs spec-identity signals beyond embeddings (see the
  full ClauseFinder project for one approach: identifier-aware hybrid
  retrieval plus a citation validator).
- Exact cosine search over a few thousand vectors is deliberate — at this
  scale a vector database would add setup cost without adding recall.

## Troubleshooting

- `NVIDIA_API_KEY is not set` — export the key in the shell running both the
  ingest script and `nat run`.
- `no markdown found for specs [...]` — spec directory names have no dots:
  `38331`, not `38.331`; check the name exists under
  `marked/<release>/<series>_series/` in the dataset.
- Embedding model errors — hosted model availability changes over time; pass
  `--embedding-model` at ingest and set the matching `embedding_model` in
  `configs/config.yml` (query and passage embeddings must come from the same
  model).
