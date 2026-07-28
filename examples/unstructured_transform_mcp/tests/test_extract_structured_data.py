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
"""Unit tests for the extract_structured_data orchestration. No network access is required."""

import json
import typing
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic import ConfigDict
from pytest_httpserver import HTTPServer

from nat_unstructured_transform_mcp.register import ExtractionTools
from nat_unstructured_transform_mcp.register import ExtractStructuredDataConfig
from nat_unstructured_transform_mcp.register import _partition_strategy_for
from nat_unstructured_transform_mcp.register import extract_source
from nat_unstructured_transform_mcp.register import extract_structured_data
from nat_unstructured_transform_mcp.register import resolve_tools

_GROUP = "unstructured_transform"


class _ToolArgs(BaseModel):
    """Permissive input-schema stand-in that accepts any tool arguments."""
    model_config = ConfigDict(extra="allow")


class _FakeTool:
    """Mimics an MCP tool exposed through a function group: JSON text in, JSON text out."""

    def __init__(self, name: str, handler: typing.Callable[..., typing.Awaitable[str]]):
        self.instance_name = f"{_GROUP}__{name}"
        self.input_schema = _ToolArgs
        self.calls: list[dict[str, typing.Any]] = []
        self._handler = handler

    async def ainvoke(self, value: _ToolArgs) -> str:
        """Record the call arguments and return the handler's canned response."""
        args = value.model_dump()
        self.calls.append(args)
        return await self._handler(**args)


class _FakeExtractionService:
    """Canned Transform MCP responses for the chained parse-then-extract flow.

    The parse job and the extraction job have distinct ids, and the shared status and
    results tools dispatch on the ``job_id`` they are given, exactly as the server does.
    """

    def __init__(self,
                 httpserver: HTTPServer,
                 parse_statuses: list[str] | None = None,
                 extraction_statuses: list[str] | None = None):
        self.file_ref = "u10d://file/test-file-ref"
        self.parse_job_id = "parse-job-1"
        self.extraction_job_id = "extract-job-1"
        self.output_ref = "u10d://output/parse-job-1_sample.json"
        self.suggested_schema = json.dumps({
            "type": "object", "properties": {
                "total": {
                    "type": "string"
                }
            }, "required": ["total"]
        })
        self.records = [{
            "filename": "sample.pdf",
            "filetype": "application/pdf",
            "processed_date_utc": "2026-07-28T10:45:04.158141Z",
            "source_file_uri": self.output_ref,
            "extracted_data": {
                "total": "42.00"
            },
        }]

        self.upload_url = httpserver.url_for("/upload/test-file-ref")
        # Registered so that an unwanted fetch of the rendered parse output would succeed
        # and show up in the request log rather than erroring out.
        self.download_url = httpserver.url_for("/download/test-file-ref")
        httpserver.expect_request("/upload/test-file-ref", method="PUT").respond_with_data("")
        httpserver.expect_request("/download/test-file-ref", method="GET").respond_with_data("# Sample")

        self._parse_statuses = list(parse_statuses or ["COMPLETED"])
        self._extraction_statuses = list(extraction_statuses or ["COMPLETED"])

        async def _request_file_upload_url(**kwargs) -> str:
            return json.dumps({
                "upload_url": self.upload_url,
                "method": "PUT",
                "headers": {
                    "Content-Type": kwargs.get("content_type", "application/octet-stream")
                },
                "file_ref": self.file_ref,
            })

        async def _start_transform_job(**_kwargs) -> str:
            return json.dumps({"job_id": self.parse_job_id, "status": "SCHEDULED"})

        async def _start_extraction_job(**_kwargs) -> str:
            return json.dumps({"job_id": self.extraction_job_id, "status": "SCHEDULED"})

        async def _suggest_extraction_schema_for_file(**_kwargs) -> str:
            return json.dumps({
                "schema": self.suggested_schema,
                "reconciliation_guidance": "Reconcile across representative documents."
            })

        def _next(statuses: list[str]) -> str:
            return statuses.pop(0) if len(statuses) > 1 else statuses[0]

        async def _check_job_status(**kwargs) -> str:
            job_id = kwargs.get("job_id")
            statuses = self._parse_statuses if job_id == self.parse_job_id else self._extraction_statuses
            return json.dumps({"job_id": job_id, "status": _next(statuses)})

        async def _get_job_results(**kwargs) -> str:
            if kwargs.get("job_id") == self.parse_job_id:
                return json.dumps({
                    "job_type":
                        "transform",
                    "job_id":
                        self.parse_job_id,
                    "files": [{
                        "filename": "sample.pdf",
                        "download_url": self.download_url,
                        "output_ref": self.output_ref,
                        "element_count": 12,
                    }],
                })
            return json.dumps({"job_type": "extraction", "job_id": self.extraction_job_id, "files": self.records})

        self.group_functions = {
            f"{_GROUP}__request_file_upload_url":
                _FakeTool("request_file_upload_url", _request_file_upload_url),
            f"{_GROUP}__start_transform_job":
                _FakeTool("start_transform_job", _start_transform_job),
            f"{_GROUP}__suggest_extraction_schema_for_file":
                _FakeTool("suggest_extraction_schema_for_file", _suggest_extraction_schema_for_file),
            f"{_GROUP}__start_extraction_job":
                _FakeTool("start_extraction_job", _start_extraction_job),
            f"{_GROUP}__check_job_status":
                _FakeTool("check_job_status", _check_job_status),
            f"{_GROUP}__get_job_results":
                _FakeTool("get_job_results", _get_job_results),
        }

    @property
    def tools(self) -> ExtractionTools:
        """Resolve the fake group into the ExtractionTools the code under test expects."""
        return resolve_tools(self.group_functions, ExtractionTools)  # type: ignore[arg-type]

    def tool(self, name: str) -> _FakeTool:
        """Return the fake tool registered under the given MCP tool name."""
        return typing.cast(_FakeTool, self.group_functions[f"{_GROUP}__{name}"])


@pytest.fixture(name="fast_config")
def fast_config_fixture() -> ExtractStructuredDataConfig:
    """Config with tiny timeouts so the polling paths run quickly in tests."""
    return ExtractStructuredDataConfig(poll_interval_seconds=0.01,
                                       parse_timeout_seconds=5.0,
                                       extraction_timeout_seconds=5.0,
                                       http_timeout_seconds=5.0)


@pytest.fixture(name="sample_document")
def sample_document_fixture(tmp_path: Path) -> Path:
    """Write a small local file for the upload path to read."""
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"%PDF-1.4 fake test document bytes")
    return document


_SUPPLIED_SCHEMA = json.dumps({"type": "object", "properties": {"total": {"type": "string"}}})


async def test_supplied_schema_drives_extraction(httpserver: HTTPServer,
                                                 fast_config: ExtractStructuredDataConfig,
                                                 sample_document: Path):
    """A caller-supplied schema is passed through and no schema suggestion is requested."""
    service = _FakeExtractionService(httpserver, parse_statuses=["IN_PROGRESS", "COMPLETED"])

    result = await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)

    assert result.schema_was_suggested is False
    assert result.filename == "sample.pdf"
    assert json.loads(result.records_json) == service.records

    assert service.tool("suggest_extraction_schema_for_file").calls == []
    assert service.tool("start_extraction_job").calls == [{
        "element_json_refs": [service.output_ref], "schema_to_extract": _SUPPLIED_SCHEMA
    }]


async def test_parse_uses_vlm_strategy_and_output_ref(httpserver: HTTPServer,
                                                      fast_config: ExtractStructuredDataConfig,
                                                      sample_document: Path):
    """The parse ahead of an extraction requests a high-fidelity strategy for a PDF."""
    service = _FakeExtractionService(httpserver)

    await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)

    assert service.tool("start_transform_job").calls == [{
        "file_refs": [service.file_ref], "stages": {
            "partition": {
                "strategy": "vlm"
            }
        }
    }]


async def test_rendered_parse_output_is_not_downloaded(httpserver: HTTPServer,
                                                       fast_config: ExtractStructuredDataConfig,
                                                       sample_document: Path):
    """Extraction consumes the output_ref, so the rendered parse output is never fetched."""
    service = _FakeExtractionService(httpserver)

    await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)

    get_requests = [request for request, _ in httpserver.log if request.method == "GET"]
    assert get_requests == []


async def test_schema_is_suggested_when_absent(httpserver: HTTPServer,
                                               fast_config: ExtractStructuredDataConfig,
                                               sample_document: Path):
    """Without a schema, the server drafts one from the parsed document and it is used."""
    service = _FakeExtractionService(httpserver)

    result = await extract_source(service.tools, fast_config, str(sample_document))

    assert result.schema_was_suggested is True
    assert service.tool("suggest_extraction_schema_for_file").calls == [{"element_json_ref": service.output_ref}]
    assert service.tool("start_extraction_job").calls == [{
        "element_json_refs": [service.output_ref], "schema_to_extract": service.suggested_schema
    }]


async def test_guidance_is_forwarded_to_both_tools(httpserver: HTTPServer,
                                                   fast_config: ExtractStructuredDataConfig,
                                                   sample_document: Path):
    """Guidance steers the suggested schema and the extraction itself."""
    service = _FakeExtractionService(httpserver)

    await extract_source(service.tools, fast_config, str(sample_document), guidance="Only monetary totals.")

    assert service.tool("suggest_extraction_schema_for_file").calls == [{
        "element_json_ref": service.output_ref, "guidance": "Only monetary totals."
    }]
    assert service.tool("start_extraction_job").calls[0]["extraction_guidance"] == "Only monetary totals."


async def test_provenance_wrapper_is_preserved(httpserver: HTTPServer,
                                               fast_config: ExtractStructuredDataConfig,
                                               sample_document: Path):
    """The result keeps the provenance fields that tie each record to its document."""
    service = _FakeExtractionService(httpserver)

    result = await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)

    record = json.loads(result.records_json)[0]
    assert set(record) == {"filename", "filetype", "processed_date_utc", "source_file_uri", "extracted_data"}
    assert record["source_file_uri"] == service.output_ref


async def test_invalid_supplied_schema_rejected(httpserver: HTTPServer,
                                                fast_config: ExtractStructuredDataConfig,
                                                sample_document: Path):
    """A schema that is not valid JSON is rejected before any job is started."""
    service = _FakeExtractionService(httpserver)

    with pytest.raises(ValueError, match="not valid JSON"):
        await extract_source(service.tools, fast_config, str(sample_document), extraction_schema="{not json")

    assert service.tool("start_transform_job").calls == []
    assert service.tool("start_extraction_job").calls == []


async def test_missing_output_ref_raises(httpserver: HTTPServer,
                                         fast_config: ExtractStructuredDataConfig,
                                         sample_document: Path):
    """A parse result without an output_ref names the missing field."""
    service = _FakeExtractionService(httpserver)

    async def _no_output_ref(**_kwargs) -> str:
        return json.dumps({"job_id": service.parse_job_id, "files": [{"filename": "sample.pdf"}]})

    service.group_functions[f"{_GROUP}__get_job_results"] = _FakeTool("get_job_results", _no_output_ref)

    with pytest.raises(RuntimeError, match="'output_ref'"):
        await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)


async def test_failed_extraction_job_names_the_job_kind(httpserver: HTTPServer,
                                                        fast_config: ExtractStructuredDataConfig,
                                                        sample_document: Path):
    """A failed extraction job reports the extraction state, not the parse state."""
    service = _FakeExtractionService(httpserver, extraction_statuses=["FAILED"])

    with pytest.raises(RuntimeError, match="Extraction job .* unexpected state 'FAILED'"):
        await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)


async def test_extraction_timeout_reports_extraction(httpserver: HTTPServer, sample_document: Path):
    """An extraction that never completes times out against its own deadline."""
    service = _FakeExtractionService(httpserver, extraction_statuses=["IN_PROGRESS"])
    config = ExtractStructuredDataConfig(poll_interval_seconds=0.01,
                                         parse_timeout_seconds=5.0,
                                         extraction_timeout_seconds=0.05,
                                         http_timeout_seconds=5.0)

    with pytest.raises(TimeoutError, match="Extraction job .* did not complete"):
        await extract_source(service.tools, config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)


async def test_empty_records_raises(httpserver: HTTPServer,
                                    fast_config: ExtractStructuredDataConfig,
                                    sample_document: Path):
    """A completed extraction that returns nothing raises rather than reporting success."""
    service = _FakeExtractionService(httpserver)
    real_results = service.tool("get_job_results")

    async def _empty_extraction(**kwargs) -> str:
        if kwargs.get("job_id") == service.extraction_job_id:
            return json.dumps({"job_type": "extraction", "job_id": service.extraction_job_id, "files": []})
        return await real_results._handler(**kwargs)

    service.group_functions[f"{_GROUP}__get_job_results"] = _FakeTool("get_job_results", _empty_extraction)

    with pytest.raises(RuntimeError, match="returned no records"):
        await extract_source(service.tools, fast_config, str(sample_document), extraction_schema=_SUPPLIED_SCHEMA)


async def test_public_url_skips_upload(httpserver: HTTPServer, fast_config: ExtractStructuredDataConfig):
    """A public URL is parsed directly, with no upload step."""
    service = _FakeExtractionService(httpserver)
    url = "https://example.com/invoice.pdf"

    await extract_source(service.tools, fast_config, url, extraction_schema=_SUPPLIED_SCHEMA)

    assert service.tool("request_file_upload_url").calls == []
    assert service.tool("start_transform_job").calls[0]["file_refs"] == [url]


def test_resolve_tools_reports_missing_extraction_tool(httpserver: HTTPServer):
    """resolve_tools names an absent extraction tool, which is the include-list contract check."""
    service = _FakeExtractionService(httpserver)
    del service.group_functions[f"{_GROUP}__start_extraction_job"]

    with pytest.raises(ValueError, match="start_extraction_job"):
        resolve_tools(service.group_functions, ExtractionTools)  # type: ignore[arg-type]


def test_shipped_config_exposes_the_extraction_tools(monkeypatch: pytest.MonkeyPatch):
    """The shipped config registers the function and includes the tools it resolves.

    ``resolve_tools`` fails fast on a missing tool, so the include list and
    ``ExtractionTools`` have to stay in step.
    """
    from nat.runtime.loader import load_config
    from nat.test.utils import locate_example_config

    monkeypatch.setenv("UNSTRUCTURED_API_KEY", "test-key-0123456789")

    config = load_config(locate_example_config(ExtractStructuredDataConfig))

    function_config = config.functions["extract_structured_data"]
    assert isinstance(function_config, ExtractStructuredDataConfig)
    assert str(function_config.mcp_group) == "unstructured_transform"

    included = set(config.function_groups["unstructured_transform"].include or [])
    assert set(ExtractionTools._fields) <= included

    assert "extract_structured_data" in config.workflow.tool_names


@pytest.mark.parametrize(
    "source, expected",
    [
        ("/tmp/report.pdf", "vlm"),
        ("/tmp/scan.PNG", "vlm"),
        ("/tmp/deck.pptx", "vlm"),
        ("/tmp/notes.docx", "fast"),
        ("/tmp/data.xlsx", "fast"),
        ("/tmp/no-suffix", "fast"),
        ("https://example.com/a/report.pdf?token=abc", "vlm"),
        ("https://example.com/a/report.docx?token=abc", "fast"),
    ],
)
def test_partition_strategy_by_input_type(source: str, expected: str):
    """Images, slides, and PDFs get a vision parse; other formats get the fast parse.

    A query string on a URL must not defeat the suffix check.
    """
    assert _partition_strategy_for(source) == expected


# --- The registered function: agent-facing wrapper contract ---


class _StubGroup:
    """Minimal function group that exposes the fake tools to the registered function."""

    def __init__(self, group_functions: dict[str, _FakeTool]):
        self._group_functions = group_functions

    async def get_accessible_functions(self) -> dict[str, _FakeTool]:
        """Return the fake group's functions."""
        return self._group_functions


class _StubBuilder:
    """Minimal builder that hands the registered function its function group."""

    def __init__(self, group: _StubGroup):
        self._group = group

    async def get_function_group(self, _name) -> _StubGroup:
        """Return the stub group regardless of the requested name."""
        return self._group


@asynccontextmanager
async def _registered_extract_info(service: _FakeExtractionService, config: ExtractStructuredDataConfig):
    """Drive the registered async generator exactly as the workflow builder would."""
    builder = _StubBuilder(_StubGroup(service.group_functions))
    async with extract_structured_data(config, builder) as info:  # type: ignore[arg-type]
        yield info


async def test_registered_input_schema_field_names(httpserver: HTTPServer, fast_config: ExtractStructuredDataConfig):
    """The generated input model exposes the three documented arguments.

    ``extraction_schema`` rather than ``schema``: the latter shadows a pydantic
    ``BaseModel`` attribute and makes the generated model emit a warning.
    """
    service = _FakeExtractionService(httpserver)

    async with _registered_extract_info(service, fast_config) as info:
        assert list(info.input_schema.model_fields) == ["source", "extraction_schema", "guidance"]


async def test_registered_function_happy_path(httpserver: HTTPServer,
                                              fast_config: ExtractStructuredDataConfig,
                                              sample_document: Path):
    """The registered tool returns the extracted records as JSON."""
    service = _FakeExtractionService(httpserver)

    async with _registered_extract_info(service, fast_config) as info:
        output = await info.single_fn(
            info.input_schema(source=str(sample_document), extraction_extraction_schema=_SUPPLIED_SCHEMA))

    assert json.loads(output) == service.records


async def test_registered_function_without_schema(httpserver: HTTPServer,
                                                  fast_config: ExtractStructuredDataConfig,
                                                  sample_document: Path):
    """Called with only a source, the tool has the server draft the schema."""
    service = _FakeExtractionService(httpserver)

    async with _registered_extract_info(service, fast_config) as info:
        output = await info.single_fn(info.input_schema(source=str(sample_document)))

    assert json.loads(output) == service.records
    assert service.tool("suggest_extraction_schema_for_file").calls == [{"element_json_ref": service.output_ref}]


async def test_registered_function_returns_error_string(httpserver: HTTPServer,
                                                        fast_config: ExtractStructuredDataConfig,
                                                        tmp_path: Path):
    """Failures must reach the agent as a readable tool result, never as an exception."""
    service = _FakeExtractionService(httpserver)
    missing = tmp_path / "does-not-exist.pdf"

    async with _registered_extract_info(service, fast_config) as info:
        output = await info.single_fn(
            info.input_schema(source=str(missing), extraction_extraction_schema=_SUPPLIED_SCHEMA))

    assert output.startswith("ERROR: failed to extract structured data")
    assert str(missing) in output


async def test_registered_function_truncates_output(httpserver: HTTPServer, sample_document: Path):
    """Output longer than the limit is truncated with a notice that the JSON is incomplete."""
    service = _FakeExtractionService(httpserver)
    config = ExtractStructuredDataConfig(poll_interval_seconds=0.01,
                                         parse_timeout_seconds=5.0,
                                         extraction_timeout_seconds=5.0,
                                         http_timeout_seconds=5.0,
                                         max_output_characters=20)

    async with _registered_extract_info(service, config) as info:
        output = await info.single_fn(
            info.input_schema(source=str(sample_document), extraction_extraction_schema=_SUPPLIED_SCHEMA))

    assert "[Output truncated at 20 characters" in output
    assert "incomplete" in output
