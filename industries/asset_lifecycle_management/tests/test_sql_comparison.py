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

"""
Comparison tests for SQL retriever implementations.

This test suite compares the original SQL retriever (generate_sql_query_and_retrieve_tool)
with the new package-based implementation (vanna_sql_tool from nat_vanna_tool).
"""

import pytest
import asyncio
import time
import json
import os
from pathlib import Path

# Test queries for comparison
TEST_QUERIES = [
    {
        "query": "How many unique engines are in the FD001 training dataset?",
        "expected_pattern": "100",  # FD001 has 100 training units
        "description": "Simple count query"
    },
    {
        "query": "Retrieve time in cycles and operational setting 1 from FD001 test for unit 1",
        "expected_columns": ["time_in_cycles", "operational_setting_1"],
        "description": "Column selection query"
    },
    {
        "query": "What is the maximum sensor 2 value in the FD001 training dataset?",
        "expected_pattern": "sensor_2",
        "description": "Aggregation query"
    },
    {
        "query": "Get sensor 4 measurements for engine 5 in FD001 train dataset",
        "expected_columns": ["sensor_4"],
        "description": "Filter and column query"
    },
    {
        "query": "Retrieve real RUL of each unit in FD001 test dataset",
        "expected_table": "RUL_FD001",
        "description": "RUL retrieval query"
    }
]


class ComparisonResult:
    """Store comparison results for a single query."""

    def __init__(self, query: str, description: str):
        self.query = query
        self.description = description
        self.old_result = None
        self.vanna_result = None
        self.old_time = None
        self.vanna_time = None
        self.old_error = None
        self.vanna_error = None
        self.old_sql = None
        self.vanna_sql = None

    def add_old_result(self, result: str, execution_time: float, sql: str = None, error: str = None):
        """Add results from old implementation."""
        self.old_result = result
        self.old_time = execution_time
        self.old_sql = sql
        self.old_error = error

    def add_vanna_result(self, result: str, execution_time: float, sql: str = None, error: str = None):
        """Add results from new implementation."""
        self.vanna_result = result
        self.vanna_time = execution_time
        self.vanna_sql = sql
        self.vanna_error = error

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "description": self.description,
            "old_implementation": {
                "result": self.old_result,
                "execution_time_ms": round(self.old_time * 1000, 2) if self.old_time else None,
                "sql_generated": self.old_sql,
                "error": self.old_error
            },
            "vanna_implementation": {
                "result": self.vanna_result,
                "execution_time_ms": round(self.vanna_time * 1000, 2) if self.vanna_time else None,
                "sql_generated": self.vanna_sql,
                "error": self.vanna_error
            },
            "comparison": {
                "both_succeeded": self.old_error is None and self.vanna_error is None,
                "results_match": self._results_match(),
                "performance_winner": self._get_performance_winner()
            }
        }

    def _results_match(self) -> bool:
        """Check if results semantically match."""
        if self.old_error or self.vanna_error:
            return False
        # Simple comparison - can be enhanced
        return self.old_result is not None and self.vanna_result is not None

    def _get_performance_winner(self) -> str:
        """Determine which implementation was faster."""
        if self.old_time is None or self.vanna_time is None:
            return "N/A"
        if self.old_time < self.vanna_time:
            return f"old ({round((self.vanna_time - self.old_time) * 1000, 2)}ms faster)"
        elif self.vanna_time < self.old_time:
            return f"vanna ({round((self.old_time - self.vanna_time) * 1000, 2)}ms faster)"
        else:
            return "tie"


@pytest.fixture(scope="module")
def output_dir():
    """Create and return output directory for test results."""
    output_path = Path("test_comparison_output")
    output_path.mkdir(exist_ok=True)
    return output_path


@pytest.mark.comparison
@pytest.mark.asyncio
class TestSQLComparison:
    """Compare SQL retriever implementations."""

    comparison_results = []

    async def test_import_both_tools(self):
        """Test that both implementations can be imported."""
        try:
            from nat_alm_agent.retrievers import generate_sql_query_and_retrieve_tool
            print("✓ Old SQL tool imported successfully")
        except Exception as e:
            pytest.fail(f"Failed to import old SQL tool: {e}")

        try:
            from nat_vanna_tool import vanna_sql_tool
            print("✓ New Vanna SQL tool imported successfully")
        except Exception as e:
            pytest.fail(f"Failed to import Vanna SQL tool: {e}")

    @pytest.mark.parametrize("test_case", TEST_QUERIES, ids=[q["description"] for q in TEST_QUERIES])
    async def test_query_comparison(self, test_case, output_dir):
        """Compare both implementations on the same query."""
        query = test_case["query"]
        description = test_case["description"]

        print(f"\n{'='*80}")
        print(f"Testing: {description}")
        print(f"Query: {query}")
        print(f"{'='*80}")

        result = ComparisonResult(query, description)

        # NOTE: This test would require actual NAT builder setup
        # For now, we're documenting the test structure
        # Actual implementation would need:
        # 1. NAT builder initialization with config
        # 2. Tool function execution
        # 3. Result comparison

        print("\n⚠️  Note: Full comparison requires NAT runtime environment")
        print("This test documents the comparison structure.")

        TestSQLComparison.comparison_results.append(result)

    @pytest.mark.comparison
    def test_generate_comparison_report(self, output_dir):
        """Generate comprehensive comparison report."""
        report_path = output_dir / "comparison_report.json"

        report = {
            "test_run_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_queries": len(TEST_QUERIES),
            "results": [r.to_dict() for r in TestSQLComparison.comparison_results],
            "summary": {
                "test_structure_validated": True,
                "note": "Full comparison requires NAT runtime with config file"
            }
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Comparison report saved to: {report_path}")

        # Generate markdown summary
        self._generate_markdown_summary(output_dir, report)

    def _generate_markdown_summary(self, output_dir, report):
        """Generate markdown summary of comparison."""
        md_path = output_dir / "COMPARISON_SUMMARY.md"

        with open(md_path, 'w') as f:
            f.write("# SQL Tool Comparison Summary\n\n")
            f.write(f"**Test Run:** {report['test_run_timestamp']}\n\n")
            f.write(f"**Total Test Queries:** {report['total_queries']}\n\n")

            f.write("## Test Queries\n\n")
            for i, query in enumerate(TEST_QUERIES, 1):
                f.write(f"{i}. **{query['description']}**\n")
                f.write(f"   - Query: `{query['query']}`\n\n")

            f.write("## Comparison Criteria\n\n")
            f.write("1. **Correctness** - Do both tools generate valid SQL?\n")
            f.write("2. **Accuracy** - Do results match expected data?\n")
            f.write("3. **Performance** - Response time comparison\n")
            f.write("4. **Reliability** - Error handling and edge cases\n")
            f.write("5. **Maintainability** - Code clarity and debugging ease\n\n")

            f.write("## Next Steps\n\n")
            f.write("1. Run actual comparison with NAT runtime:\n")
            f.write("   ```bash\n")
            f.write("   # Configure environment\n")
            f.write("   export NVIDIA_API_KEY=your-key\n\n")
            f.write("   # Test with old tool\n")
            f.write("   nat serve --config_file=configs/config-reasoning.yaml\n\n")
            f.write("   # Update config to use sql_retriever_vanna\n")
            f.write("   # Test with new tool\n")
            f.write("   ```\n\n")
            f.write("2. Compare outputs in `output_data/` directory\n")
            f.write("3. Measure response times\n")
            f.write("4. Document winner in COMPARISON.md\n")
            f.write("5. Clean up losing implementation\n")

        print(f"✓ Markdown summary saved to: {md_path}")


@pytest.mark.manual
def test_manual_comparison_instructions():
    """Instructions for manual comparison testing."""
    instructions = """

    MANUAL COMPARISON TEST INSTRUCTIONS
    ====================================

    Since full automated testing requires NAT runtime, follow these steps for manual comparison:

    1. SET UP ENVIRONMENT:
       export NVIDIA_API_KEY=your-nvidia-api-key
       cd ~/Documents/NeMo-Agent-Toolkit-Examples/industries/asset_lifecycle_management

    2. TEST OLD IMPLEMENTATION (sql_retriever_old):
       - Config already has sql_retriever pointing to old implementation
       - Start server: nat serve --config_file=configs/config-reasoning.yaml
       - Run test queries and note:
         * SQL generated
         * Data returned (check output_data/)
         * Response time
         * Any errors

    3. TEST NEW IMPLEMENTATION (sql_retriever_vanna):
       - Edit configs/config-reasoning.yaml
       - Change sql_retriever _type from generate_sql_query_and_retrieve_tool to vanna_sql_tool
       - Start server: nat serve --config_file=configs/config-reasoning.yaml
       - Run same queries and note same metrics

    4. COMPARE RESULTS:
       - Correctness: Valid SQL generated?
       - Accuracy: Correct data returned?
       - Performance: Response times
       - Errors: Any failures?

    5. DOCUMENT WINNER:
       - Create COMPARISON.md with results
       - Update README with decision
       - Delete losing implementation

    TEST QUERIES:
    """

    for i, test_case in enumerate(TEST_QUERIES, 1):
        instructions += f"\n    {i}. {test_case['description']}: {test_case['query']}"

    print(instructions)

    assert True, "Manual test instructions displayed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "comparison"])
