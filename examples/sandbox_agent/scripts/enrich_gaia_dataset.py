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
"""Enrich GAIA dataset by prepending attachment file paths to questions.

The original GAIA dataset's Question column contains only the question text.
When there's an attachment file, the agent has no way to know which file in
/workspace/input/ belongs to the current task (files are UUID-named).

This script prepends "[Attached file for this task: /workspace/input/{file_name}]"
to questions that have attachments, so the agent can directly use the correct file.

Usage:
    # From the sandbox_agent directory:
    python scripts/enrich_gaia_dataset.py

    # With custom input/output paths:
    python scripts/enrich_gaia_dataset.py \
        --input data/attachments/metadata.parquet \
        --output data/gaia_validation_enriched.parquet

    # Read directly from HuggingFace:
    python scripts/enrich_gaia_dataset.py \
        --input hf://datasets/gaia-benchmark/GAIA/2023/validation/metadata.parquet
"""

import argparse
from pathlib import Path

import pandas as pd

# Default paths relative to the package data directory
_SCRIPT_DIR = Path(__file__).resolve().parent
_PACKAGE_DATA_DIR = _SCRIPT_DIR.parent / "src" / "nat_sandbox_agent" / "data"
_DEFAULT_INPUT = _PACKAGE_DATA_DIR / "attachments" / "metadata.parquet"
_DEFAULT_OUTPUT = _PACKAGE_DATA_DIR / "gaia_validation_enriched.parquet"

# Prefix template for attached files
_ATTACHMENT_PREFIX = "[Attached file for this task: /workspace/input/{file_name}]"


def enrich_dataset(input_path: str, output_path: str) -> None:
    """Enrich GAIA dataset by prepending file paths to questions with attachments.

    Args:
        input_path: Path to original GAIA metadata.parquet (local or HF URL).
        output_path: Path to write the enriched parquet file.
    """
    print(f"Reading dataset from: {input_path}")
    df = pd.read_parquet(input_path)

    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # Identify rows with attachments
    has_file = df["file_name"].notna() & (df["file_name"] != "")
    attachment_count = has_file.sum()
    print(f"Rows with attachments: {attachment_count}")

    # Prepend file path to questions that have attachments
    enriched_count = 0
    for idx in df[has_file].index:
        file_name = df.at[idx, "file_name"]
        original_question = df.at[idx, "Question"]

        # Skip if already enriched (idempotent)
        if original_question.startswith("[Attached file"):
            continue

        prefix = _ATTACHMENT_PREFIX.format(file_name=file_name)
        df.at[idx, "Question"] = f"{prefix}\n\n{original_question}"
        enriched_count += 1

    print(f"Enriched {enriched_count} questions (skipped {attachment_count - enriched_count} already enriched)")

    # Write output
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"Written enriched dataset to: {output_path}")

    # Show a sample
    sample = df[has_file].iloc[0]
    print("\nSample enriched question (first 200 chars):")
    print(f"  {sample['Question'][:200]}")


def main():
    parser = argparse.ArgumentParser(description="Enrich GAIA dataset with attachment file paths")
    parser.add_argument(
        "--input",
        "-i",
        default=str(_DEFAULT_INPUT),
        help=f"Input parquet path (default: {_DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(_DEFAULT_OUTPUT),
        help=f"Output parquet path (default: {_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    enrich_dataset(args.input, args.output)


if __name__ == "__main__":
    main()
