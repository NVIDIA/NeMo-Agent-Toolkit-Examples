#!/usr/bin/env python3
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
Direct test script for E2B sandbox functionality.

This script tests the E2B sandbox without going through the full NAT workflow.
Useful for quick verification and debugging.

Usage:
    export E2B_API_KEY="your-key"
    python test_e2b_sandbox.py
"""

import asyncio
import os
import sys
from pathlib import Path


async def test_simple_execution():
    """Test 1: Simple print statement"""
    print("\n" + "="*80)
    print("TEST 1: Simple Code Execution")
    print("="*80)

    from src.nat_alm_agent.code_execution.e2b_sandbox import E2BSandbox

    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        print("❌ E2B_API_KEY not set!")
        return False

    sandbox = E2BSandbox(
        api_key=api_key,
        workspace_files_dir="output_data",
        timeout=30.0
    )

    code = """
print("Hello from E2B cloud sandbox!")
print("Python version:", __import__('sys').version)
"""

    result = await sandbox.execute_code(code, timeout_seconds=10.0)

    print(f"Status: {result['process_status']}")
    print(f"Stdout:\n{result['stdout']}")
    if result['stderr']:
        print(f"Stderr:\n{result['stderr']}")

    # Join stdout list into string for checking
    stdout_text = ''.join(result['stdout']) if isinstance(result['stdout'], list) else result['stdout']
    success = result['process_status'] == 'completed' and 'Hello from E2B' in stdout_text
    print(f"\n{'✅ PASSED' if success else '❌ FAILED'}")
    return success


async def test_file_generation():
    """Test 2: Generate and download a file"""
    print("\n" + "="*80)
    print("TEST 2: File Generation and Download")
    print("="*80)

    from src.nat_alm_agent.code_execution.e2b_sandbox import E2BSandbox

    api_key = os.environ.get("E2B_API_KEY")
    sandbox = E2BSandbox(
        api_key=api_key,
        workspace_files_dir="output_data",
        timeout=30.0
    )

    code = """
import json

data = {
    "message": "E2B test successful",
    "status": "working",
    "test": "file_generation"
}

with open("e2b_test.json", "w") as f:
    json.dump(data, f, indent=2)

print("File created: e2b_test.json")
"""

    result = await sandbox.execute_code(code, timeout_seconds=10.0)

    print(f"Status: {result['process_status']}")
    print(f"Stdout:\n{result['stdout']}")
    print(f"Downloaded files: {result.get('downloaded_files', [])}")

    # Check if file was downloaded
    test_file = Path("output_data/e2b_test.json")
    file_exists = test_file.exists()

    if file_exists:
        print(f"\n✅ File downloaded: {test_file}")
        print(f"Content: {test_file.read_text()}")
    else:
        print(f"\n❌ File not found: {test_file}")

    success = result['process_status'] == 'completed' and file_exists
    print(f"\n{'✅ PASSED' if success else '❌ FAILED'}")
    return success


async def test_data_processing():
    """Test 3: Data processing with pandas"""
    print("\n" + "="*80)
    print("TEST 3: Data Processing (Pandas)")
    print("="*80)

    from src.nat_alm_agent.code_execution.e2b_sandbox import E2BSandbox

    api_key = os.environ.get("E2B_API_KEY")
    sandbox = E2BSandbox(
        api_key=api_key,
        workspace_files_dir="output_data",
        timeout=30.0
    )

    code = """
import pandas as pd
import json

# Create sample data
df = pd.DataFrame({
    'x': [1, 2, 3, 4, 5],
    'y': [2, 4, 6, 8, 10]
})

# Calculate statistics
result = {
    "rows": len(df),
    "sum_x": int(df['x'].sum()),
    "sum_y": int(df['y'].sum()),
    "mean_x": float(df['x'].mean())
}

# Save results
with open("pandas_test.json", "w") as f:
    json.dump(result, f, indent=2)

print(f"Processed {len(df)} rows")
print(f"Sum of x: {result['sum_x']}")
print(f"Sum of y: {result['sum_y']}")
"""

    result = await sandbox.execute_code(code, timeout_seconds=15.0)

    print(f"Status: {result['process_status']}")
    print(f"Stdout:\n{result['stdout']}")
    print(f"Downloaded files: {result.get('downloaded_files', [])}")

    # Check results
    test_file = Path("output_data/pandas_test.json")
    file_exists = test_file.exists()

    if file_exists:
        import json
        data = json.loads(test_file.read_text())
        print(f"\n✅ Results: {data}")
        correct = data['sum_x'] == 15 and data['sum_y'] == 30
        success = result['process_status'] == 'completed' and correct
    else:
        print(f"\n❌ File not found: {test_file}")
        success = False

    print(f"\n{'✅ PASSED' if success else '❌ FAILED'}")
    return success


async def test_utils_upload():
    """Test 4: Upload and use workspace utils"""
    print("\n" + "="*80)
    print("TEST 4: Workspace Utils Upload")
    print("="*80)

    from src.nat_alm_agent.code_execution.e2b_sandbox import E2BSandbox

    # Check if utils exist
    utils_path = Path("output_data/utils")
    if not utils_path.exists():
        print(f"⚠️  Utils directory not found at {utils_path}")
        print("Skipping this test. To enable, run: cp -r utils_template output_data/utils")
        return None  # Skip test

    api_key = os.environ.get("E2B_API_KEY")
    sandbox = E2BSandbox(
        api_key=api_key,
        workspace_files_dir="output_data",
        timeout=30.0
    )

    code = """
import sys
sys.path.append("/home/user")

try:
    import utils
    print("✅ Utils imported successfully")
    print(f"Utils location: {utils.__file__}")

    # Try to call show_utilities if it exists
    if hasattr(utils, 'show_utilities'):
        utils.show_utilities()
    else:
        print("show_utilities() not found, but import worked")

except Exception as e:
    print(f"❌ Error importing utils: {e}")
    import traceback
    traceback.print_exc()
"""

    result = await sandbox.execute_code(code, timeout_seconds=15.0)

    print(f"Status: {result['process_status']}")
    print(f"Stdout:\n{result['stdout']}")
    if result['stderr']:
        print(f"Stderr:\n{result['stderr']}")

    # Join stdout list into string for checking
    stdout_text = ''.join(result['stdout']) if isinstance(result['stdout'], list) else result['stdout']
    success = result['process_status'] == 'completed' and 'Utils imported successfully' in stdout_text
    print(f"\n{'✅ PASSED' if success else '❌ FAILED'}")
    return success


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("E2B SANDBOX TEST SUITE")
    print("="*80)

    # Check prerequisites
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        print("\n❌ ERROR: E2B_API_KEY environment variable not set!")
        print("\nTo fix this:")
        print("  1. Sign up at https://e2b.dev/auth/sign-up")
        print("  2. Get your API key from https://e2b.dev/dashboard")
        print("  3. Run: export E2B_API_KEY='your-key-here'")
        return

    # Ensure output directory exists
    Path("output_data").mkdir(exist_ok=True)

    # Run tests
    results = []

    try:
        results.append(("Simple Execution", await test_simple_execution()))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Simple Execution", False))

    try:
        results.append(("File Generation", await test_file_generation()))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("File Generation", False))

    try:
        results.append(("Data Processing", await test_data_processing()))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Data Processing", False))

    try:
        utils_result = await test_utils_upload()
        if utils_result is not None:
            results.append(("Utils Upload", utils_result))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Utils Upload", False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)

    for name, result in results:
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        print(f"{name:25} {status}")

    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if skipped > 0:
        print(f"Skipped: {skipped}")

    if failed == 0 and passed > 0:
        print("\n🎉 All tests passed! E2B integration is working correctly.")
    elif failed > 0:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())
