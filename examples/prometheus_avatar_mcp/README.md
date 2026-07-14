<!--
SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Prometheus Avatar MCP Example

**Complexity:** Intermediate

This example gives an NVIDIA NeMo Agent Toolkit agent an **embodied avatar** (a body it
can create, speak through, and share) by attaching the open-source
[Prometheus Avatar MCP server](https://github.com/myths-labs/prometheus-avatar)
(`@prometheusavatar/mcp-server` on npm) as a tool source. The agent reasons over natural-language requests ("create an avatar and
introduce yourself") and calls the avatar tools to return a live talking avatar you can embed.

This example is intentionally hosted in the examples repository because it depends on an
external MCP server (`@prometheusavatar/mcp-server`, published to npm) whose data, schema,
availability, and responses are not controlled by the toolkit. It is useful as a reference
integration for wiring an agent to a rich, third-party MCP tool source over `stdio`; the
primary MCP end-to-end examples in the toolkit are the self-contained client/server
examples in the main repository.

## What the Agent Can Do

The Prometheus Avatar MCP server exposes nine tools. This example wires them all in and
lets the agent choose which to call:

| Tool | Description |
|------|-------------|
| `create_avatar` | Create a new embodied avatar (model, voice, persona). Returns an embed URL. |
| `speak` | Make the avatar speak text with TTS and lip-sync animation. |
| `list_marketplace` | Browse marketplace assets (skins, voices, effects) by category. |
| `equip_asset` | Equip or remove a marketplace asset on the avatar. |
| `get_avatar_status` | Get the current avatar state and equipped assets. |
| `share_avatar` | Generate a shareable link and embed code for the avatar. |
| `generate_asset` | AI-generate a new asset from a text prompt (requires `GEMINI_API_KEY`). |
| `update_asset` | Edit price, name, description, tags, or license of a marketplace asset. |
| `generate_image_pro` | High-quality image generation (BYOK `OPENAI_API_KEY`, or platform quota). |

`create_avatar`, `speak`, and `share_avatar` require a `PROMETHEUS_API_KEY` (a `pak_`
agent key). They persist to and authenticate against your Prometheus account.
`generate_asset` and `generate_image_pro` additionally need a `GEMINI_API_KEY` /
`OPENAI_API_KEY`.

## Prerequisites

- Clone this repository and create the development environment described in the root
  [README](../../README.md).
- NeMo Agent Toolkit installed with MCP and LangChain support
  (`nvidia-nat[langchain,mcp]`).
- [Node.js](https://nodejs.org) 18+ available on your `PATH`. The avatar server is an npm
  package launched with `npx`.
- An LLM to drive the agent. This example defaults to an
  [NVIDIA NIM](https://build.nvidia.com) model (`nvidia/nemotron-3-nano-30b-a3b`); set
  `NVIDIA_API_KEY` with a key from the NVIDIA build portal. To use an OpenAI-compatible endpoint
  instead, see [Using a Different LLM](#using-a-different-llm).

## Configuration

The `config.yml` registers the avatar server as an `mcp_client` function group over the
`stdio` transport:

```yaml
function_groups:
  prometheus_avatar:
    _type: mcp_client
    server:
      transport: stdio
      command: npx
      args: ["-y", "@prometheusavatar/mcp-server"]
```

NeMo Agent Toolkit launches the server, discovers the tools it exposes, and makes them
available to the workflow agent. The snippet above is abbreviated; the full
[`configs/config.yml`](configs/config.yml) also sets an `env:` block (which injects
`PROMETHEUS_API_KEY`) and `tool_overrides` (which steer tool selection).

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_API_KEY` | Yes (for the default NIM LLM) | Key from the [NVIDIA build portal](https://build.nvidia.com). |
| `PROMETHEUS_API_KEY` | Yes (for `create_avatar`, `speak`, `share_avatar`) | Prometheus agent key (`pak_...`), register via `POST https://prometheus.mythslabs.ai/api/agent/register`. |
| `GEMINI_API_KEY` | Only for `generate_asset` | Google AI key ([free tier](https://ai.google.dev)). |
| `OPENAI_API_KEY` | Only for `generate_image_pro` (BYOK) | OpenAI key with image generation access. |

`config.yml` passes `PROMETHEUS_API_KEY` into the avatar server via its `env:` block;
`export PROMETHEUS_API_KEY=pak_...` before running. Enable the optional keys in
`config.yml` as needed.

## Usage

Run the workflow from the root directory of this repository:

```bash
export NVIDIA_API_KEY="nvapi-..."
export PROMETHEUS_API_KEY="pak_..."
nat run --config_file examples/prometheus_avatar_mcp/configs/config.yml \
  --input "Create an avatar of a friendly guide, have it say 'Hello! I'm your NeMo agent.', then share it"
```

The agent will call `create_avatar`, `speak`, and `share_avatar`, and return an embed URL.
Open the URL in a browser to see the avatar render and speak.

## Discover the Avatar Tools (No LLM Required)

You can list the tools the avatar server exposes without running the agent. Useful for
prototyping and debugging:

```bash
nat mcp client tool list \
  --transport stdio \
  --command npx \
  --args "-y @prometheusavatar/mcp-server"
```

Add `--tool create_avatar` to inspect a single tool's input schema.

## Configuration Details

### MCP Client Setup

The configuration connects to the Prometheus Avatar MCP server using:
- **Transport**: `stdio` (the server is a local `npx`-launched process)
- **Command**: `npx -y @prometheusavatar/mcp-server`
- **Tool overrides**: `create_avatar` and `speak` are given clearer descriptions so the
  agent selects them reliably.

### Using a Different LLM

The `llms.nim_llm` block can be swapped for any provider NeMo Agent Toolkit supports. For
an OpenAI-compatible endpoint, replace it with:

```yaml
llms:
  nim_llm:
    _type: openai
    model_name: gpt-4o-mini
```

and set `OPENAI_API_KEY`. The rest of the configuration is unchanged.

## Troubleshooting

### `npx` cannot be found

Ensure Node.js 18+ is installed and `npx` is on your `PATH` (`npx --version`). The first
run downloads the avatar server package, which may take a moment.

### The agent does not call the expected tool

The `react_agent` chooses tools from their descriptions. Add or refine entries under
`tool_overrides` in `config.yml` to steer it, as shown for `create_avatar` and `speak`.

### Authenticated operations fail

`create_avatar`, `speak`, and `share_avatar` require `PROMETHEUS_API_KEY` (a `pak_` agent
key): they persist to and authenticate against your Prometheus account. `list_marketplace`
and `get_avatar_status` are read-only and work without a key. `generate_asset` additionally
needs `GEMINI_API_KEY`, and `generate_image_pro` needs `OPENAI_API_KEY` (BYOK). Export the
required keys in your shell; `config.yml` forwards them to the server via its `env:` block
(enable the optional ones as needed).

## References

- [NeMo Agent Toolkit MCP Client Documentation](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/build-workflows/mcp-client.md)
- [Prometheus Avatar MCP server](https://github.com/myths-labs/prometheus-avatar) (`@prometheusavatar/mcp-server` on npm)
- [Prometheus platform](https://prometheus.mythslabs.ai)
