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

# Document Transformation with the Unstructured Transform MCP Server

**Complexity:** Intermediate

This example demonstrates how the NVIDIA NeMo Agent Toolkit connects to a third-party remote MCP server that is protected by static bearer-token authentication: the hosted [Unstructured Transform](https://transform.unstructured.io/get-started) service, which converts documents (PDF, DOCX, PPTX, XLSX, HTML, images, and 40+ other formats) into clean Markdown that agents can reason over.

It also demonstrates a useful composition pattern: the remote MCP server exposes an asynchronous, multi-step protocol, and this example wraps that protocol in deterministic custom functions so the agent only needs one reliable tool call. Two functions are registered, one that converts a document to Markdown and one that extracts named fields from it as JSON.

This example is hosted in the examples repository because it requires an Unstructured API key and depends on an external MCP server whose data, schema, availability, and responses are not controlled by the toolkit. It is a reference integration, and it targets NeMo Agent Toolkit 1.8.

## Key Features

- **Bearer-token MCP authentication:** Uses the `api_key` authentication provider with `auth_scheme: Bearer` to authenticate against a remote MCP server with a static API key supplied through an environment variable. The other MCP examples in the NeMo Agent Toolkit cover unauthenticated servers and OAuth2 flows; this example covers the common "API key in a header" case.
- **Remote MCP client over streamable HTTP:** Declares the Transform server as an `mcp_client` function group using the `streamable-http` transport.
- **Deterministic composition of MCP tools:** A custom function (`transform_document`) resolves the four Transform MCP tools from the function group and orchestrates the upload, transform, poll, and download flow in plain Python, exposing one dependable tool to the ReAct agent.
- **Chaining two async jobs:** A second function (`extract_structured_data`) shows the same pattern over a dependent pair of jobs, parsing a document and then extracting named fields from the parse output as JSON.
- **Document parsing for agents:** Turns binary documents into Markdown the LLM can summarize, query, and extract from.

## How It Works

The Unstructured Transform MCP server exposes an asynchronous job protocol. Four tools cover parsing:

1. `request_file_upload_url`: Returns a pre-signed upload URL and a file reference for a local file.
2. `start_transform_job`: Starts a transform job for one or more file references (or public HTTP(S) URLs) and returns a job ID.
3. `check_job_status`: Reports whether the job is `SCHEDULED`, `IN_PROGRESS`, or `COMPLETED` (any other state means the job failed, and the function reports it as an error).
4. `get_job_results`: Returns a pre-signed download URL for the Markdown output of each transformed file.

Two more cover structured data extraction, described in [Structured Data Extraction](#structured-data-extraction) below:

5. `suggest_extraction_schema_for_file`: Drafts a JSON Schema from one parsed document.
6. `start_extraction_job`: Runs an extraction against a JSON Schema and returns a job ID. Status and results come from the same two tools as a parse.

Two steps of the protocol are plain HTTP transfers rather than MCP calls: uploading the raw document bytes to the pre-signed upload URL and downloading the Markdown from the pre-signed download URL. An agent cannot perform those byte transfers with MCP tools alone, and letting an LLM drive the polling loop is slow and unreliable. The `transform_document` function in `src/nat_unstructured_transform_mcp/register.py` therefore performs the whole sequence deterministically:

```text
agent -> transform_document(source)
           |-- request_file_upload_url (MCP)      # local files only
           |-- PUT raw bytes to upload URL        # plain HTTP, no bearer token
           |-- start_transform_job (MCP)
           |-- check_job_status (MCP)             # polled until COMPLETED
           |-- get_job_results (MCP)
           `-- GET Markdown from download URL     # plain HTTP, no bearer token
```

The function accepts either a local file path or a public HTTP(S) URL (public URLs are passed directly to `start_transform_job`, skipping the upload). Transforms take from a few seconds up to several minutes depending on page count, and the maximum file size is 50 MB. Each `transform_document` call processes a single document, and the example always requests the default Markdown output; the Transform service also supports element JSON, HTML, and plain-text output, which would require extending `transform_document`.

> [!IMPORTANT]
> Trust boundary: for a local path, `transform_document` reads that file and uploads its contents to the hosted Transform service. Because the path comes from the agent, a crafted prompt could point it at a sensitive file (for example a private key or a credentials file) and cause that file to leave the host. Run this example with documents and prompts you trust, and if you adapt it for untrusted input, restrict the accepted paths to a designated directory. The same applies to `extract_structured_data`, which takes a path the same way.

### Structured Data Extraction

`extract_structured_data` returns named fields as JSON instead of the whole document as text, which is what you want for invoices, forms, and contracts. It shows the composition pattern over two *dependent* jobs, because the extractor reads the Element JSON a parse produces rather than a raw file:

```text
agent -> extract_structured_data(source, extraction_schema, guidance)
           |-- request_file_upload_url (MCP)              # local files only
           |-- PUT raw bytes to upload URL                # plain HTTP, no bearer token
           |-- start_transform_job (MCP)                  # with a partition strategy
           |-- check_job_status / get_job_results (MCP)   # polled; yields output_ref
           |-- suggest_extraction_schema_for_file (MCP)   # only when no schema is given
           |-- start_extraction_job (MCP)                 # consumes the output_ref
           `-- check_job_status / get_job_results (MCP)   # polled; returns JSON inline
```

Three details of that flow are worth knowing if you adapt it:

- **The `output_ref` is the handle, not the rendered output.** Each file entry in the results of a completed parse carries a durable `output_ref` alongside its `download_url`, and it is present whichever output format you render. The function passes that reference straight to the extractor and never downloads the Markdown, which saves a transfer of output nobody reads.
- **Parse fidelity sets the quality ceiling.** The extractor can only surface what the parse captured, so the function picks the partition strategy from the input type: `vlm` for PDFs, images, and PowerPoint files, and `fast` for everything else, where the higher-fidelity strategies silently fall back anyway. If a result comes back sparse, re-parsing with `hi_res` plus the `image_description`, `generative_ocr`, and `table_to_html` enrichment steps is the documented next step.
- **Results keep their provenance.** Each record wraps `extracted_data` with `filename`, `filetype`, `processed_date_utc`, and `source_file_uri`. The function returns the whole wrapper rather than the bare data, since that is what ties a record back to the document it came from.

The schema is optional. Pass `extraction_schema` as a JSON Schema encoded in a JSON string to fix the output shape, or leave it out and the server drafts one from the document itself. `guidance` is free text that steers both the drafted schema and how fields are filled. The agent-facing argument is deliberately named `extraction_schema` rather than `schema`, because these parameter names become fields of a generated Pydantic model and `schema` shadows a `BaseModel` attribute.

## Prerequisites

1. **Unstructured Transform API key:** Sign up and create a key at [transform.unstructured.io/get-started](https://transform.unstructured.io/get-started).
2. **NVIDIA API key:** The workflow uses an NVIDIA NIM hosted model. Get your key from the [NVIDIA API Catalog](https://build.nvidia.com/).
3. **NeMo Agent Toolkit development environment:** Clone this repository and create the development environment described in the root [README](../../README.md). Installing this example (below) pulls in the toolkit with MCP and LangChain support from PyPI.

## Installation and Setup

### Install this Workflow

From the root of the repository, run:

```bash
uv pip install -e examples/unstructured_transform_mcp
```

### Set Up API Keys

```bash
export UNSTRUCTURED_API_KEY=<YOUR_UNSTRUCTURED_API_KEY>
export NVIDIA_API_KEY=<YOUR_NVIDIA_API_KEY>
```

## Run the Workflow

Ask the agent to transform a document and answer a question about it. The input can be a public HTTPS URL:

```bash
nat run --config_file examples/unstructured_transform_mcp/configs/config.yml \
  --input "Transform https://arxiv.org/pdf/1706.03762 to Markdown and list the section headings."
```

Or a local file:

<!-- path-check-skip-begin -->
```bash
nat run --config_file examples/unstructured_transform_mcp/configs/config.yml \
  --input "Transform the document at /path/to/your/document.pdf and summarize it in three bullet points."
```
<!-- path-check-skip-end -->

**Expected Workflow Output**

The transform takes roughly one to three minutes for this 15-page paper, after which the agent answers from the returned Markdown:

```text
Workflow Result:
The section headings of the transformed document are:
- # Attention Is All You Need
- # 2 Background
- # 3 Model Architecture
- # 3.1 Encoder and Decoder Stacks
- # 3.2 Attention
- # 3.2.1 Scaled Dot-Product Attention
- # 3.2.2 Multi-Head Attention
- # 3.3 Position-wise Feed-Forward Networks
- # 3.4 Embeddings and Softmax
- # 3.5 Positional Encoding
- # 4 Why Self-Attention
- # 5 Training
- # 5.1 Training Data and Batching
- # 5.2 Hardware and Schedule
- # 5.3 Optimizer
- # 5.4 Regularization
- # 6 Results
- # 6.1 Machine Translation
- # 6.2 Model Variations
- # 6.3 English Constituency Parsing
- # 7 Conclusion
- # References
```

### Extract Structured Data

Ask for named fields instead, and the agent picks `extract_structured_data`:

```bash
nat run --config_file examples/unstructured_transform_mcp/configs/config.yml \
  --input "Extract each plant's name, light needs, watering instructions, and humidity level from https://docs.unstructured.io/img/pipelines/data-extractor/house-plant-care.png as JSON."
```

The agent parses the image, has the server draft a schema (no schema was supplied), runs the extraction, and returns one record per document:

```text
Workflow Result:
[
  {
    "filename": "house-plant-care.png",
    "filetype": "image/png",
    "processed_date_utc": "2026-07-28T10:45:04.158141Z",
    "source_file_uri": "u10d://output/<parse-job-id>_house-plant-care.json",
    "extracted_data": {
      "plants": [
        {
          "plant_name": "MONSTERA DELICIOSA",
          "light_requirements": "Bright Indirect - Some direct",
          "watering_instructions": "Water when 80% dry",
          "humidity_level": "Low - Medium"
        }
      ]
    }
  }
]
```

## Configuration Details

The complete configuration is in `configs/config.yml`. The MCP client and authentication sections are the interesting parts:

```yaml
function_groups:
  unstructured_transform:
    _type: mcp_client
    server:
      transport: streamable-http
      url: https://mcp.transform.unstructured.io
      auth_provider: unstructured_auth
    include:
      - request_file_upload_url
      - start_transform_job
      - suggest_extraction_schema_for_file
      - start_extraction_job
      - check_job_status
      - get_job_results

authentication:
  unstructured_auth:
    _type: api_key
    raw_key: ${UNSTRUCTURED_API_KEY}
    auth_scheme: Bearer
```

- The `api_key` authentication provider attaches `Authorization: Bearer <UNSTRUCTURED_API_KEY>` to every request the MCP client makes, including the initial handshake.
- `${UNSTRUCTURED_API_KEY}` is interpolated from the environment when the configuration is loaded. See [workflow configuration](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/build-workflows/workflow-configuration.md) for the interpolation syntax.
- The `include` list documents the six tools the example depends on and fails fast if the server stops exposing any of them.
- Both functions reference the function group through their `mcp_group` setting, so the group does not need to appear in the workflow `tool_names` and the agent never sees the low-level tools.

### Alternative: Custom Headers

If you prefer not to define an authentication provider, the MCP client can also send a static header directly. This variant sends the same header but does not retry on authentication failures:

```yaml
function_groups:
  unstructured_transform:
    _type: mcp_client
    server:
      transport: streamable-http
      url: https://mcp.transform.unstructured.io
      custom_headers:
        Authorization: "Bearer ${UNSTRUCTURED_API_KEY}"
    include:
      - request_file_upload_url
      - start_transform_job
      - suggest_extraction_schema_for_file
      - start_extraction_job
      - check_job_status
      - get_job_results
```

Keep the `include` list in this variant as well; it provides the same fail-fast contract check described above.

### Tuning

The `transform_document` function accepts a few settings in the `functions` section of the configuration:

| Setting | Default | Purpose |
|---|---|---|
| `poll_interval_seconds` | `5.0` | Delay between job status checks. |
| `transform_timeout_seconds` | `900.0` | Maximum time to wait for a transform job. Raise this for very large documents. |
| `http_timeout_seconds` | `120.0` | Timeout for the raw upload and download requests. |
| `max_file_size_bytes` | `52428800` | Maximum document size accepted by the Transform service (50 MB at the time of writing). |
| `max_output_characters` | `50000` | Truncates the returned Markdown to protect the context window of the agent; a short truncation notice is appended. |

`extract_structured_data` takes the same settings, except that it splits the job timeout in two because it runs a parse and then an extraction:

| Setting | Default | Purpose |
|---|---|---|
| `poll_interval_seconds` | `5.0` | Delay between job status checks. |
| `parse_timeout_seconds` | `900.0` | Maximum time to wait for the parse that precedes the extraction. |
| `extraction_timeout_seconds` | `600.0` | Maximum time to wait for the extraction job itself. |
| `http_timeout_seconds` | `120.0` | Timeout for the raw upload request. |
| `max_file_size_bytes` | `52428800` | Maximum document size accepted by the Transform service (50 MB at the time of writing). |
| `max_output_characters` | `50000` | Truncates the returned JSON to protect the context window of the agent. Truncated output is no longer valid JSON, so the appended notice says so. |

## Testing

Unit tests mock the MCP tools and the HTTP transfers, so they run without network access or credentials:

```bash
pytest examples/unstructured_transform_mcp/tests
```

Integration tests run against the live Transform service and are skipped unless `UNSTRUCTURED_API_KEY` is set (the full workflow test also requires `NVIDIA_API_KEY`):

```bash
pytest --run_integration --run_slow examples/unstructured_transform_mcp/tests
```

## Troubleshooting

- **Authentication errors during startup:** A missing `UNSTRUCTURED_API_KEY` fails configuration validation immediately with a `raw_key` error, because the environment variable interpolates to an empty string. An invalid key fails the MCP handshake when the workflow is built. In both cases, verify the variable is exported in the shell that runs `nat run`.
- **Transform timed out:** Large documents can take several minutes. Raise `transform_timeout_seconds` in the `transform_document` function configuration.
- **Transform job ended in an unexpected state:** The document could not be processed on the server (for example, a corrupt or unsupported file). The error includes the status payload returned by the service.
- **File too large:** The Transform service accepts files up to 50 MB.
- **Document not found:** The agent passes the file path verbatim, so use an absolute path in the prompt.

## Related Examples and Documentation

- [`kaggle_mcp`](../kaggle_mcp/README.md): Another remote MCP server reached over `streamable-http` with bearer-token authentication.
- [MCP client documentation](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/build-workflows/mcp-client.md): All `mcp_client` configuration options.
- [API authentication documentation](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/components/auth/api-authentication.md): Details of the `api_key` authentication provider.
- [Unstructured structured data extraction](https://docs.unstructured.io/transform/sde): How the extractor works, and prompt patterns for it.
