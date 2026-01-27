# SPDX-FileCopyrightText: Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

import logging
from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class E2BCodeExecutionToolConfig(FunctionBaseConfig, name="e2b_code_execution"):
    """
    Tool for executing Python code in E2B cloud-hosted sandbox environment.

    E2B provides:
    - Cloud-hosted execution (no Docker setup required)
    - Automatic workspace management
    - File upload/download capabilities
    - Fast sandbox startup (~150ms)

    Use this instead of local Docker sandbox when:
    - Docker is not available or desired
    - Running in CI/CD environments
    - Multi-user or production deployments
    - Network access is available
    """

    e2b_api_key: str = Field(
        description="E2B API key (get from https://e2b.dev/dashboard). Can use ${E2B_API_KEY} env var"
    )
    workspace_files_dir: str = Field(
        description="Path to local workspace directory for file uploads/downloads (e.g., 'output_data')"
    )
    timeout: float = Field(
        default=30.0,
        description="Timeout in seconds for code execution (E2B needs more time for file transfers)"
    )
    max_output_characters: int = Field(
        default=2000,
        description="Maximum number of characters in stdout/stderr"
    )


@register_function(config_type=E2BCodeExecutionToolConfig)
async def e2b_code_execution_tool(config: E2BCodeExecutionToolConfig, builder: Builder):
    """
    Execute Python code in E2B cloud sandbox.

    This tool:
    1. Creates ephemeral E2B sandbox
    2. Uploads workspace files (utils/, database/, etc.)
    3. Executes the provided code
    4. Downloads generated files
    5. Returns execution results

    The sandbox is automatically cleaned up after execution.
    """
    from .e2b_sandbox import E2BSandbox

    class CodeExecutionInputSchema(BaseModel):
        generated_code: str = Field(description="Python code to execute in E2B sandbox")

    # Create E2B sandbox instance
    sandbox = E2BSandbox(
        api_key=config.e2b_api_key,
        workspace_files_dir=config.workspace_files_dir,
        timeout=config.timeout
    )

    logger.info("E2B code execution tool initialized")

    async def _execute_code(generated_code: str) -> dict:
        """
        Execute code in E2B cloud sandbox.

        Args:
            generated_code: Python code to execute

        Returns:
            Dictionary containing:
                - process_status: "completed", "error", or "timeout"
                - stdout: Standard output
                - stderr: Standard error
                - downloaded_files: List of downloaded file paths
        """
        logger.info("Executing code in E2B cloud sandbox...")

        try:
            result = await sandbox.execute_code(
                generated_code=generated_code,
                timeout_seconds=config.timeout,
                language="python",
                max_output_characters=config.max_output_characters,
            )

            # Log downloaded files
            if result.get("downloaded_files"):
                logger.info(f"Downloaded {len(result['downloaded_files'])} files from E2B sandbox")
                for file_path in result["downloaded_files"]:
                    logger.debug(f"  - {file_path}")

            return result

        except Exception as e:
            logger.exception(f"Error executing code in E2B sandbox: {e}")
            return {
                "process_status": "error",
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "downloaded_files": []
            }

    yield FunctionInfo.from_fn(
        fn=_execute_code,
        input_schema=CodeExecutionInputSchema,
        description="""Executes the provided Python code in an E2B cloud-hosted sandbox.

        E2B provides isolated cloud execution without requiring Docker:
        - Automatic workspace setup with utils and database files
        - File upload/download for inputs and outputs
        - Fast sandbox startup (~150ms)
        - Secure execution environment

        Returns a dictionary with execution status, stdout, stderr, and list of downloaded files.
        Generated files are automatically downloaded to the local workspace directory."""
    )
