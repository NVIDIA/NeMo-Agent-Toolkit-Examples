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
"""Register the ``transform_document`` and ``extract_structured_data`` functions.

The Unstructured Transform MCP server exposes an asynchronous, multi-step protocol
(request an upload URL, upload the raw bytes over plain HTTP, start a transform job,
poll for completion, download the result). ``transform_document`` composes those MCP tools
into a single deterministic function so the agent only needs one reliable tool call.

``extract_structured_data`` adds the server's structured data extraction tools on top of
that flow. Extraction consumes the Element JSON a parse produces rather than a raw file,
so it is a second asynchronous job chained onto the first: parse the document, take the
``output_ref`` of the completed parse, optionally have the server draft a JSON Schema for
it, then run the extraction and poll it with the same status and results tools.
"""

import asyncio
import json
import logging
import mimetypes
import typing
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function import Function
from nat.builder.function import FunctionGroup
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import FunctionGroupRef
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)

# Maximum file size accepted by the Unstructured Transform service (50 MB).
MAX_FILE_SIZE_BYTES = 52_428_800

# Job states reported by the check_job_status MCP tool which mean "keep waiting".
_PENDING_JOB_STATES = frozenset({"SCHEDULED", "IN_PROGRESS"})
_COMPLETED_JOB_STATE = "COMPLETED"

# The MCP client converts transport-level failures into plain-text tool output; the
# idempotent polling calls tolerate this many consecutive such failures before giving up.
_MAX_CONSECUTIVE_POLL_FAILURES = 3


class TransformDocumentConfig(FunctionBaseConfig, name="transform_document"):
    """Configuration for the ``transform_document`` function."""

    mcp_group: FunctionGroupRef = Field(
        default=FunctionGroupRef("unstructured_transform"),
        description="Reference to the mcp_client function group connected to the Unstructured Transform MCP server.")
    poll_interval_seconds: float = Field(default=5.0, gt=0, description="Delay between transform job status checks.")
    transform_timeout_seconds: float = Field(
        default=900.0,
        gt=0,
        description="Maximum time to wait for a transform job to complete. Large documents take longer.")
    http_timeout_seconds: float = Field(
        default=120.0, gt=0, description="Timeout for the plain HTTP file upload and result download requests.")
    max_file_size_bytes: int = Field(
        default=MAX_FILE_SIZE_BYTES,
        gt=0,
        description="Maximum document size accepted by the Transform service (50 MB at the time of writing).")
    max_output_characters: int = Field(
        default=50_000,
        gt=0,
        description="Truncate the returned Markdown body beyond this length to protect the context window of the "
        "agent. A short truncation notice is appended to truncated output.")


class TransformResult(BaseModel):
    """Outcome of a single document transform."""

    markdown: str
    element_count: int
    character_count: int
    filename: str


class TransformTools(typing.NamedTuple):
    """The four Unstructured Transform MCP tools, resolved from the function group."""

    request_file_upload_url: Function
    start_transform_job: Function
    check_job_status: Function
    get_job_results: Function


class ExtractionTools(typing.NamedTuple):
    """The Transform MCP tools needed to parse a document and then extract from it.

    A superset of ``TransformTools``: extraction runs on the Element JSON of a completed
    parse, so the parse tools are required as well as the two extraction tools.
    """

    request_file_upload_url: Function
    start_transform_job: Function
    suggest_extraction_schema_for_file: Function
    start_extraction_job: Function
    check_job_status: Function
    get_job_results: Function


# The helpers below drive whichever job kind they are given, so they accept either bundle.
AnyTools = TransformTools | ExtractionTools

_ToolsT = typing.TypeVar("_ToolsT", TransformTools, ExtractionTools)


def resolve_tools(group_functions: dict[str, Function],
                  tools_type: type[_ToolsT] = TransformTools) -> _ToolsT:  # type: ignore[assignment]
    """Look up the Transform MCP tools in a function group by their MCP tool names.

    Function groups expose members as ``<group_instance>__<tool_name>``; the tool name is
    recovered with the framework ``FunctionGroup.decompose`` helper.

    Args:
        group_functions: Accessible functions of the mcp_client function group.
        tools_type: The bundle to resolve, naming the tools that are required.

    Returns:
        The resolved Transform MCP tools.

    Raises:
        ValueError: If a required tool is not present in the function group.
    """
    by_tool_name = {FunctionGroup.decompose(full_name)[1]: fn for full_name, fn in group_functions.items()}

    missing = [name for name in tools_type._fields if name not in by_tool_name]
    if missing:
        raise ValueError(f"Required MCP tools {missing} were not found in the function group. "
                         f"Available tools: {sorted(by_tool_name)}")

    return tools_type(**{name: by_tool_name[name] for name in tools_type._fields})


class MCPToolError(RuntimeError):
    """Raised when a Transform MCP tool returns an error payload."""

    def __init__(self, tool_name: str, code: str, message: str):
        self.code = code
        super().__init__(f"The '{tool_name}' MCP tool returned an error ({code}): {message}")


async def _invoke_tool(tool: Function, **tool_args: typing.Any) -> dict[str, typing.Any]:
    """Invoke an MCP tool and parse its JSON text content into a dictionary."""
    raw = await tool.ainvoke(tool.input_schema(**tool_args))
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(f"Expected a JSON payload from the '{tool.instance_name}' MCP tool but received: "
                           f"{str(raw)[:300]!r}") from e
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object from the '{tool.instance_name}' MCP tool but received: "
                           f"{str(raw)[:300]!r}")
    error = payload.get("error")
    if isinstance(error, dict):
        raise MCPToolError(tool.instance_name, str(error.get("code", "unknown")), str(error.get("message", error)))
    return payload


def _require(payload: dict[str, typing.Any], key: str, tool_name: str) -> typing.Any:
    """Return a required key from an MCP tool payload, or raise a descriptive error."""
    try:
        return payload[key]
    except KeyError as e:
        raise RuntimeError(f"The '{tool_name}' MCP tool response is missing the required '{key}' field: "
                           f"{str(payload)[:300]!r}") from e


def _check_http_response(response: httpx.Response, description: str) -> None:
    """Raise a descriptive error for a failed HTTP transfer without leaking the pre-signed URL.

    The query string of a pre-signed URL carries its signature, which is a credential. This
    error message reaches logs and the agent, so it includes only the scheme, host, and path.
    """
    if response.status_code >= 400:
        safe_url = response.request.url.copy_with(query=None, fragment=None)
        raise RuntimeError(f"The {description} failed with HTTP {response.status_code} from {safe_url}")


async def _upload_source(tools: AnyTools, http_client: httpx.AsyncClient, source: str, max_file_size_bytes: int) -> str:
    """Return a file reference for the document, uploading local files first.

    Public HTTP or HTTPS URLs are passed through unchanged because the start_transform_job
    MCP tool accepts them directly. Local files are uploaded to a pre-signed URL minted
    by the request_file_upload_url MCP tool.
    """
    if source.startswith(("http://", "https://")):
        return source

    path = Path(source).expanduser()
    # Filesystem access is offloaded to a worker thread so the reads (up to the size limit)
    # do not block the event loop, per the async I/O guideline.
    if not await asyncio.to_thread(path.is_file):
        raise FileNotFoundError(f"Document not found: {source}")

    size_bytes = (await asyncio.to_thread(path.stat)).st_size
    if size_bytes > max_file_size_bytes:
        raise ValueError(f"Document is {size_bytes} bytes which exceeds the "
                         f"{max_file_size_bytes} byte limit of the Transform service.")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    upload = await _invoke_tool(tools.request_file_upload_url,
                                filename=path.name,
                                content_type=content_type,
                                size_bytes=size_bytes)

    # Upload the raw bytes to the pre-signed URL. This is a plain HTTP request, not an
    # MCP call, and the pre-signed URL must not receive the bearer token.
    file_bytes = await asyncio.to_thread(path.read_bytes)
    response = await http_client.request(str(upload.get("method", "PUT")),
                                         _require(upload, "upload_url", "request_file_upload_url"),
                                         content=file_bytes,
                                         headers=upload.get("headers") or {})
    _check_http_response(response, "document upload")

    return _require(upload, "file_ref", "request_file_upload_url")


def _timeout_error(job_id: str, timeout_seconds: float, job_kind: str = "Transform") -> TimeoutError:
    return TimeoutError(f"{job_kind} job {job_id} did not complete within {timeout_seconds} seconds. "
                        "Large documents can take several minutes; consider raising the job timeout.")


async def _wait_for_job(tools: AnyTools,
                        job_id: str,
                        poll_interval_seconds: float,
                        deadline: float,
                        timeout_seconds: float,
                        job_kind: str = "Transform") -> None:
    """Poll the transform job status until it completes, fails, or times out.

    Transport-level blips (which the MCP client surfaces as plain-text tool output rather
    than exceptions) are retried a few times so a momentary hiccup does not abandon a
    long-running server-side job.
    """
    loop = asyncio.get_running_loop()
    consecutive_failures = 0

    while True:
        try:
            status_payload = await _invoke_tool(tools.check_job_status, job_id=job_id)
        except MCPToolError:
            raise
        except RuntimeError:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_POLL_FAILURES or loop.time() >= deadline:
                raise
            logger.warning("Status check for %s job %s failed (%d consecutive); retrying",
                           job_kind.lower(),
                           job_id,
                           consecutive_failures)
            await asyncio.sleep(poll_interval_seconds)
            continue
        consecutive_failures = 0

        status = str(status_payload.get("status", "")).upper()

        if status == _COMPLETED_JOB_STATE:
            return
        if status not in _PENDING_JOB_STATES:
            raise RuntimeError(f"{job_kind} job {job_id} ended in unexpected state '{status}': "
                               f"{str(status_payload)[:300]!r}")
        if loop.time() >= deadline:
            raise _timeout_error(job_id, timeout_seconds, job_kind)

        logger.debug("%s job %s is %s; polling again in %.1f seconds", job_kind, job_id, status, poll_interval_seconds)
        await asyncio.sleep(poll_interval_seconds)


async def _fetch_results(tools: AnyTools,
                         job_id: str,
                         poll_interval_seconds: float,
                         deadline: float,
                         timeout_seconds: float,
                         job_kind: str = "Transform") -> dict[str, typing.Any]:
    """Fetch the transform results, tolerating the brief window after the job reports completion.

    The status endpoint can report ``COMPLETED`` slightly before the results are
    materialized, in which case get_job_results returns a ``job_not_complete``
    error. Retry within the overall transform deadline. Transport-level blips are retried
    the same way as in the status loop.
    """
    loop = asyncio.get_running_loop()
    consecutive_failures = 0

    while True:
        try:
            return await _invoke_tool(tools.get_job_results, job_id=job_id)
        except MCPToolError as e:
            if e.code != "job_not_complete":
                raise
            # The server reports job_not_complete as a JSON error envelope inside a
            # successful (isError=false) tool result; this is the observed behavior of the
            # brief status-vs-results consistency window and is safe to retry.
            if loop.time() >= deadline:
                raise _timeout_error(job_id, timeout_seconds, job_kind) from e
            consecutive_failures = 0
        except RuntimeError:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_POLL_FAILURES or loop.time() >= deadline:
                raise
            logger.warning("Results fetch for %s job %s failed (%d consecutive); retrying",
                           job_kind.lower(),
                           job_id,
                           consecutive_failures)

        logger.debug("%s job %s results are not ready yet; polling again in %.1f seconds",
                     job_kind,
                     job_id,
                     poll_interval_seconds)
        await asyncio.sleep(poll_interval_seconds)


async def transform_source(tools: TransformTools, config: TransformDocumentConfig, source: str) -> TransformResult:
    """Run the full upload, transform, poll, and download flow for one document.

    Args:
        tools: The resolved Transform MCP tools.
        config: The function configuration.
        source: Local file path or public HTTP or HTTPS URL of the document.

    Returns:
        The transformed document as Markdown plus transform metadata.
    """
    async with httpx.AsyncClient(timeout=config.http_timeout_seconds) as http_client:
        file_ref = await _upload_source(tools, http_client, source, config.max_file_size_bytes)

        job = await _invoke_tool(tools.start_transform_job, file_refs=[file_ref])
        job_id = _require(job, "job_id", "start_transform_job")
        logger.info("Started transform job %s for '%s'", job_id, source)

        # The status wait and the results fetch share one overall deadline.
        deadline = asyncio.get_running_loop().time() + config.transform_timeout_seconds
        await _wait_for_job(tools, job_id, config.poll_interval_seconds, deadline, config.transform_timeout_seconds)

        results = await _fetch_results(tools,
                                       job_id,
                                       config.poll_interval_seconds,
                                       deadline,
                                       config.transform_timeout_seconds)
        files = results.get("files")
        if not isinstance(files, list) or not files:
            raise RuntimeError(f"Transform job {job_id} completed but returned no files.")
        first_file = files[0]
        if not isinstance(first_file, dict):
            raise RuntimeError(f"Transform job {job_id} returned an unexpected files entry: "
                               f"{str(first_file)[:300]!r}")

        # The download URL is pre-signed as well, so no bearer token is sent here either.
        download = await http_client.get(_require(first_file, "download_url", "get_job_results"))
        _check_http_response(download, "result download")

        return TransformResult(markdown=download.text,
                               element_count=int(first_file.get("element_count") or 0),
                               character_count=int(first_file.get("character_count") or len(download.text)),
                               filename=str(first_file.get("filename") or Path(source).name))


@register_function(config_type=TransformDocumentConfig)
async def transform_document(config: TransformDocumentConfig, builder: Builder):
    """Register the ``transform_document`` function.

    Resolves the four Unstructured Transform MCP tools from the configured mcp_client
    function group and exposes the whole flow to the agent as one tool.
    """
    group = await builder.get_function_group(config.mcp_group)
    tools = resolve_tools(await group.get_accessible_functions())

    async def _transform(source: str) -> str:
        """Transform a document into Markdown.

        Args:
            source: Local file path or public HTTP or HTTPS URL of the document.

        Returns:
            The document content converted to Markdown, or an error description.
        """
        try:
            result = await transform_source(tools, config, source)
        except (OSError, ValueError, RuntimeError, TimeoutError, httpx.HTTPError, httpx.InvalidURL) as e:
            logger.exception("Failed to transform '%s'", source)
            return f"ERROR: failed to transform '{source}': {e}"

        logger.info("Transformed '%s': %d elements, %d characters",
                    result.filename,
                    result.element_count,
                    result.character_count)

        markdown = result.markdown
        if len(markdown) > config.max_output_characters:
            markdown = (f"{markdown[:config.max_output_characters]}\n\n"
                        f"[Output truncated at {config.max_output_characters} characters. The full document has "
                        f"{result.character_count} characters.]")
        return markdown

    yield FunctionInfo.from_fn(
        _transform,
        description=("Convert a document (PDF, DOCX, PPTX, XLSX, HTML, images, and 40+ other formats) into "
                     "clean Markdown using the Unstructured Transform service. The input must be either the path to "
                     "a local file or a public HTTP or HTTPS URL of the document. Returns the extracted content as "
                     "Markdown. Transformation is asynchronous on the server and can take from a few seconds up to "
                     "several minutes depending on document size."))


class ExtractStructuredDataConfig(FunctionBaseConfig, name="extract_structured_data"):
    """Configuration for the ``extract_structured_data`` function."""

    mcp_group: FunctionGroupRef = Field(
        default=FunctionGroupRef("unstructured_transform"),
        description="Reference to the mcp_client function group connected to the Unstructured Transform MCP server.")
    poll_interval_seconds: float = Field(default=5.0, gt=0, description="Delay between job status checks.")
    parse_timeout_seconds: float = Field(
        default=900.0,
        gt=0,
        description="Maximum time to wait for the parse that precedes an extraction. Large documents take longer.")
    extraction_timeout_seconds: float = Field(default=600.0,
                                              gt=0,
                                              description="Maximum time to wait for the extraction job itself.")
    http_timeout_seconds: float = Field(default=120.0,
                                        gt=0,
                                        description="Timeout for the plain HTTP file upload request.")
    max_file_size_bytes: int = Field(
        default=MAX_FILE_SIZE_BYTES,
        gt=0,
        description="Maximum document size accepted by the Transform service (50 MB at the time of writing).")
    max_output_characters: int = Field(
        default=50_000,
        gt=0,
        description="Truncate the returned JSON beyond this length to protect the context window of the agent. "
        "Truncated output is no longer valid JSON, so a notice saying so is appended.")


class ExtractionResult(BaseModel):
    """Outcome of a structured data extraction over one document."""

    records_json: str
    filename: str
    schema_was_suggested: bool


# Input types whose parse quality benefits from a vision model reading the page. The
# server's guidance is to start with the vlm strategy for these, and to use fast for
# everything else, where vlm and hi_res silently fall back to fast anyway. Extraction can
# only surface what the parse captured, so this choice sets the quality ceiling.
_VLM_PARTITION_SUFFIXES = frozenset({
    ".bmp",
    ".heic",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".tif",
    ".tiff",
    ".webp",
})


def _partition_strategy_for(source: str) -> str:
    """Return the parse strategy to use for a document that will be extracted from."""
    path = urlsplit(source).path if source.startswith(("http://", "https://")) else source
    return "vlm" if Path(path).suffix.lower() in _VLM_PARTITION_SUFFIXES else "fast"


async def _parse_to_output_ref(tools: ExtractionTools,
                               config: ExtractStructuredDataConfig,
                               http_client: httpx.AsyncClient,
                               source: str) -> tuple[str, str]:
    """Parse the document and return the Element JSON reference the extractor consumes.

    Returns:
        The completed parse job's ``output_ref`` and the filename the server reported.
    """
    file_ref = await _upload_source(tools, http_client, source, config.max_file_size_bytes)

    stages = {"partition": {"strategy": _partition_strategy_for(source)}}
    job = await _invoke_tool(tools.start_transform_job, file_refs=[file_ref], stages=stages)
    job_id = _require(job, "job_id", "start_transform_job")
    logger.info("Started parse job %s for '%s' ahead of extraction", job_id, source)

    deadline = asyncio.get_running_loop().time() + config.parse_timeout_seconds
    await _wait_for_job(tools, job_id, config.poll_interval_seconds, deadline, config.parse_timeout_seconds, "Parse")
    results = await _fetch_results(tools,
                                   job_id,
                                   config.poll_interval_seconds,
                                   deadline,
                                   config.parse_timeout_seconds,
                                   "Parse")

    files = results.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError(f"Parse job {job_id} completed but returned no files.")
    first_file = files[0]
    if not isinstance(first_file, dict):
        raise RuntimeError(f"Parse job {job_id} returned an unexpected files entry: {str(first_file)[:300]!r}")

    # The rendered output is deliberately not downloaded. The extractor consumes the
    # durable Element JSON handle, which is present whichever output format was rendered,
    # so fetching the Markdown here would transfer a result nobody reads.
    output_ref = _require(first_file, "output_ref", "get_job_results")
    return str(output_ref), str(first_file.get("filename") or Path(source).name)


async def _suggest_schema(tools: ExtractionTools, output_ref: str, guidance: str | None) -> str:
    """Ask the server to draft a JSON Schema for a parsed document."""
    args: dict[str, typing.Any] = {"element_json_ref": output_ref}
    if guidance:
        args["guidance"] = guidance

    payload = await _invoke_tool(tools.suggest_extraction_schema_for_file, **args)
    schema = _require(payload, "schema", "suggest_extraction_schema_for_file")
    # The tool returns the schema as a JSON string; tolerate an object for robustness.
    return schema if isinstance(schema, str) else json.dumps(schema)


async def extract_source(tools: ExtractionTools,
                         config: ExtractStructuredDataConfig,
                         source: str,
                         extraction_schema: str | None = None,
                         guidance: str | None = None) -> ExtractionResult:
    """Parse one document, then extract structured data from it against a JSON Schema.

    Args:
        tools: The resolved Transform MCP tools.
        config: The function configuration.
        source: Local file path or public HTTP or HTTPS URL of the document.
        extraction_schema: JSON Schema as a JSON string. When omitted, the server drafts one.
        guidance: Free-text guidance on which fields matter and how to fill them.

    Returns:
        The extracted records as JSON, with provenance, plus which schema was used.

    Raises:
        ValueError: If a supplied schema is not valid JSON.
    """
    if extraction_schema is not None:
        try:
            json.loads(extraction_schema)
        except json.JSONDecodeError as e:
            raise ValueError(f"The supplied extraction schema is not valid JSON: {e}") from e

    async with httpx.AsyncClient(timeout=config.http_timeout_seconds) as http_client:
        output_ref, filename = await _parse_to_output_ref(tools, config, http_client, source)

        schema_was_suggested = extraction_schema is None
        if extraction_schema is None:
            extraction_schema = await _suggest_schema(tools, output_ref, guidance)
            logger.info("The server drafted an extraction schema for '%s'", filename)

        extraction_args: dict[str, typing.Any] = {
            "element_json_refs": [output_ref], "schema_to_extract": extraction_schema
        }
        if guidance:
            extraction_args["extraction_guidance"] = guidance

        job = await _invoke_tool(tools.start_extraction_job, **extraction_args)
        job_id = _require(job, "job_id", "start_extraction_job")
        logger.info("Started extraction job %s for '%s'", job_id, filename)

        deadline = asyncio.get_running_loop().time() + config.extraction_timeout_seconds
        await _wait_for_job(tools,
                            job_id,
                            config.poll_interval_seconds,
                            deadline,
                            config.extraction_timeout_seconds,
                            "Extraction")
        results = await _fetch_results(tools,
                                       job_id,
                                       config.poll_interval_seconds,
                                       deadline,
                                       config.extraction_timeout_seconds,
                                       "Extraction")

    files = results.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError(f"Extraction job {job_id} completed but returned no records.")

    # Each entry wraps extracted_data with the provenance that ties it back to its source
    # document: filename, filetype, processed_date_utc, and source_file_uri. The whole
    # wrapper is returned rather than the bare data so that audit trail is not lost.
    return ExtractionResult(records_json=json.dumps(files, indent=2),
                            filename=filename,
                            schema_was_suggested=schema_was_suggested)


@register_function(config_type=ExtractStructuredDataConfig)
async def extract_structured_data(config: ExtractStructuredDataConfig, builder: Builder):
    """Register the ``extract_structured_data`` function.

    Resolves the parse and extraction MCP tools from the configured mcp_client function
    group and exposes the chained parse-then-extract flow to the agent as one tool.
    """
    group = await builder.get_function_group(config.mcp_group)
    tools = resolve_tools(await group.get_accessible_functions(), ExtractionTools)

    # The agent-facing parameter is deliberately not called "schema": these names become
    # fields of a generated Pydantic input model, and "schema" shadows a BaseModel attribute.
    async def _extract(source: str, extraction_schema: str = "", guidance: str = "") -> str:
        """Extract structured data from a document as JSON.

        Args:
            source: Local file path or public HTTP or HTTPS URL of the document.
            extraction_schema: Optional JSON Schema, as a JSON string, naming the fields to
                extract. When empty, the server drafts a schema from the document itself.
            guidance: Optional free text describing which fields matter.

        Returns:
            The extracted records as JSON, or an error description.
        """
        try:
            result = await extract_source(tools, config, source, extraction_schema or None, guidance or None)
        except (OSError, ValueError, RuntimeError, TimeoutError, httpx.HTTPError, httpx.InvalidURL) as e:
            logger.exception("Failed to extract structured data from '%s'", source)
            return f"ERROR: failed to extract structured data from '{source}': {e}"

        logger.info("Extracted structured data from '%s' using a schema %s",
                    result.filename,
                    "drafted by the server" if result.schema_was_suggested else "supplied by the caller")

        records_json = result.records_json
        if len(records_json) > config.max_output_characters:
            return (f"{records_json[:config.max_output_characters]}\n\n"
                    f"[Output truncated at {config.max_output_characters} characters, so the JSON above is "
                    f"incomplete. The full result has {len(records_json)} characters. Extract fewer fields, or "
                    f"raise max_output_characters.]")
        return records_json

    yield FunctionInfo.from_fn(
        _extract,
        description=("Extract specific named fields from a document (PDF, DOCX, PPTX, XLSX, HTML, images, and 40+ "
                     "other formats) as structured JSON, using the Unstructured Transform service. Prefer this over "
                     "transform_document when the user wants named values such as an invoice's line items or a "
                     "form's answers, rather than the whole document as text. 'source' must be the path to a local "
                     "file or a public HTTP or HTTPS URL. 'extraction_schema' is optional: pass a JSON Schema as a "
                     "JSON string to fix the output shape, or leave it out to have the server draft one from the "
                     "document. "
                     "'guidance' is optional free text describing which fields matter. Returns one JSON record per "
                     "document, wrapping the extracted data with the source filename. The document is parsed first "
                     "and the extraction runs as a second asynchronous job, so this can take from a few seconds up "
                     "to several minutes."))
