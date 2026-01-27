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
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class E2BSandbox:
    """
    E2B cloud-hosted sandbox with file transfer capabilities.

    This sandbox provides:
    - Cloud-hosted Python execution (no Docker required)
    - Automatic workspace setup with utils and database files
    - File upload/download for inputs and outputs
    - Isolated execution environment
    """

    def __init__(
        self,
        api_key: str,
        workspace_files_dir: str,
        timeout: float = 30.0
    ):
        """
        Initialize E2B sandbox.

        Args:
            api_key: E2B API key (will be set as E2B_API_KEY environment variable)
            workspace_files_dir: Local directory path for file transfers (e.g., "output_data")
            timeout: Default timeout in seconds for sandbox operations
        """
        # E2B SDK v2.x requires API key as environment variable
        if api_key:
            os.environ['E2B_API_KEY'] = api_key
        self.workspace_dir = Path(workspace_files_dir)
        self.timeout = timeout

        logger.info(f"E2B Sandbox initialized with workspace: {self.workspace_dir}")

    def _setup_workspace(self, sandbox) -> None:
        """
        Upload workspace files to E2B sandbox.

        Uploads to /home/user in the sandbox:
        1. utils/ directory - Pre-built utility functions (uploaded to /home/user/utils/)
        2. database/ - SQLite database file (uploaded to /home/user/database/nasa_turbo.db)

        Args:
            sandbox: Active E2B sandbox instance
        """
        logger.info("Setting up E2B sandbox workspace...")

        # 1. Upload utils directory
        utils_path = self.workspace_dir / "utils"
        if utils_path.exists() and utils_path.is_dir():
            logger.info(f"Uploading utils from {utils_path}")

            # Upload each Python file in utils using files.write() API
            for file_path in utils_path.glob("*.py"):
                with open(file_path, 'r') as f:
                    content = f.read()
                target_path = f"/home/user/utils/{file_path.name}"
                sandbox.files.write(target_path, content)
                logger.debug(f"Uploaded {file_path.name} to {target_path}")
        else:
            logger.warning(f"Utils directory not found at {utils_path}")

        # 2. Upload database file
        db_path = self.workspace_dir.parent / "database" / "nasa_turbo.db"
        if db_path.exists():
            logger.info(f"Uploading database from {db_path}")

            # Read database as bytes and upload using files.write() API
            with open(db_path, 'rb') as f:
                sandbox.files.write("/home/user/database/nasa_turbo.db", f)
            logger.debug(f"Uploaded database ({db_path.stat().st_size} bytes)")
        else:
            logger.warning(f"Database not found at {db_path}")

        logger.info("Workspace setup complete")

    def _download_outputs(self, sandbox, output_extensions: tuple = ('.json', '.html', '.png', '.jpg', '.csv', '.pdf')) -> list[str]:
        """
        Download generated files from sandbox to local filesystem.

        Args:
            sandbox: Active E2B sandbox instance
            output_extensions: Tuple of file extensions to download

        Returns:
            List of local file paths that were downloaded
        """
        logger.info("Downloading output files from E2B sandbox...")
        downloaded_files = []

        try:
            # List all files in /home/user directory using files.list() API
            files = sandbox.files.list("/home/user")

            for file_info in files:
                file_name = file_info.name if hasattr(file_info, 'name') else str(file_info)

                # Skip directories and non-output files
                if not any(file_name.endswith(ext) for ext in output_extensions):
                    continue

                # Skip files that are in subdirectories (utils, database)
                if '/' in file_name:
                    continue

                try:
                    # Read file content from sandbox using files.read() API
                    sandbox_path = f"/home/user/{file_name}"
                    content = sandbox.files.read(sandbox_path)

                    # Write to local filesystem
                    local_path = self.workspace_dir / file_name

                    # Handle both text and binary content
                    if isinstance(content, bytes):
                        local_path.write_bytes(content)
                    else:
                        local_path.write_text(content)

                    downloaded_files.append(str(local_path))
                    logger.debug(f"Downloaded {file_name} to {local_path}")

                except Exception as e:
                    logger.error(f"Failed to download {file_name}: {e}")

            logger.info(f"Downloaded {len(downloaded_files)} files")

        except Exception as e:
            logger.error(f"Error listing/downloading files: {e}")

        return downloaded_files

    async def execute_code(
        self,
        generated_code: str,
        timeout_seconds: float = 10.0,
        language: str = "python",
        max_output_characters: int = 2000,
    ) -> dict[str, str]:
        """
        Execute code in E2B cloud sandbox.

        Args:
            generated_code: Python code to execute
            timeout_seconds: Execution timeout
            language: Programming language (currently only "python")
            max_output_characters: Maximum characters in output

        Returns:
            Dictionary with:
                - process_status: "completed", "error", or "timeout"
                - stdout: Standard output from execution
                - stderr: Standard error from execution
                - downloaded_files: List of downloaded file paths (E2B-specific)
        """
        if language != "python":
            return {
                "process_status": "error",
                "stdout": "",
                "stderr": f"Language '{language}' not supported. E2B sandbox only supports Python.",
                "downloaded_files": []
            }

        logger.info("Executing code in E2B cloud sandbox...")

        try:
            # Import E2B SDK
            try:
                from e2b_code_interpreter import Sandbox
            except ImportError:
                return {
                    "process_status": "error",
                    "stdout": "",
                    "stderr": "E2B SDK not installed. Run: pip install e2b-code-interpreter",
                    "downloaded_files": []
                }

            # Create E2B sandbox using Sandbox.create() method
            # Note: E2B SDK v2.x reads API key from E2B_API_KEY environment variable
            # The timeout parameter is for sandbox lifecycle, not code execution timeout
            with Sandbox.create() as sandbox:
                logger.debug("E2B sandbox created successfully")

                # Setup workspace (upload utils, database, etc.)
                self._setup_workspace(sandbox)

                # Execute the code
                logger.debug(f"Executing code ({len(generated_code)} chars)...")
                execution = sandbox.run_code(generated_code)

                # Parse execution results
                stdout = ""
                stderr = ""
                status = "completed"

                # Extract output from execution object
                if hasattr(execution, 'logs'):
                    stdout = execution.logs.stdout if hasattr(execution.logs, 'stdout') else ""
                    stderr = execution.logs.stderr if hasattr(execution.logs, 'stderr') else ""

                # Check for text output
                if hasattr(execution, 'text') and execution.text:
                    stdout += str(execution.text)

                # Check for errors
                if hasattr(execution, 'error') and execution.error:
                    status = "error"
                    stderr += str(execution.error)

                # Download generated files
                downloaded_files = self._download_outputs(sandbox)

                # Truncate output if needed
                if len(stdout) > max_output_characters:
                    stdout = stdout[:max_output_characters] + "\n<output truncated>"

                if len(stderr) > max_output_characters:
                    stderr = stderr[:max_output_characters] + "\n<error truncated>"

                logger.info(f"Execution {status}: {len(downloaded_files)} files downloaded")

                return {
                    "process_status": status,
                    "stdout": stdout,
                    "stderr": stderr,
                    "downloaded_files": downloaded_files
                }

        except Exception as e:
            logger.exception(f"E2B sandbox execution failed: {e}")
            return {
                "process_status": "error",
                "stdout": "",
                "stderr": f"E2B sandbox error: {str(e)}",
                "downloaded_files": []
            }
