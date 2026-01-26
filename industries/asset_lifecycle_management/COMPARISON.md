# SQL Tool Comparison Results

**Date:** 2026-01-25
**Status:** Ready for Testing
**Environment:** alm conda environment with Python 3.12.12

## Overview

This document compares two SQL retriever implementations for the Asset Lifecycle Management Agent:

1. **sql_retriever_old** - Original implementation (`generate_sql_query_and_retrieve_tool`)
   - Location: `src/nat_alm_agent/retrievers/generate_sql_query_and_retrieve_tool.py`
   - Uses VannaManager singleton pattern
   - ChromaDB vector store at `database/`

2. **sql_retriever_vanna** - New package-based implementation (`vanna_sql_tool`)
   - Location: `packages/nat_vanna_tool/src/nat_vanna_tool/vanna_sql_tool.py`
   - Standalone reusable NAT tool package
   - ChromaDB vector store at `database_vanna/`

## Test Setup

Both implementations are configured in `configs/config-reasoning.yaml`:

```yaml
functions:
  # Original implementation (currently active as sql_retriever)
  sql_retriever_old:
    _type: generate_sql_query_and_retrieve_tool
    vector_store_path: "database"
    ...

  # New package implementation
  sql_retriever_vanna:
    _type: vanna_sql_tool
    vector_store_path: "database_vanna"
    ...

  # Active tool (change _type to switch implementations)
  sql_retriever:
    _type: generate_sql_query_and_retrieve_tool  # <-- Change this to vanna_sql_tool to test new implementation
    ...
```

## Test Queries

| # | Description | Query |
|---|-------------|-------|
| 1 | Simple count | How many unique engines are in the FD001 training dataset? |
| 2 | Column selection | Retrieve time in cycles and operational setting 1 from FD001 test for unit 1 |
| 3 | Aggregation | What is the maximum sensor 2 value in the FD001 training dataset? |
| 4 | Filter and column | Get sensor 4 measurements for engine 5 in FD001 train dataset |
| 5 | RUL retrieval | Retrieve real RUL of each unit in FD001 test dataset |

## Testing Instructions

### 1. Test Old Implementation

```bash
# Activate environment
conda activate alm

# Set API key
export NVIDIA_API_KEY=your-nvidia-api-key

# Config already uses sql_retriever_old by default
cd ~/Documents/NeMo-Agent-Toolkit-Examples/industries/asset_lifecycle_management

# Start NAT server
nat serve --config_file=configs/config-reasoning.yaml

# In another terminal, test queries
# (or use the web UI at http://localhost:8000)
```

Run each test query and record:
- SQL generated
- Data returned (check `output_data/`)
- Response time
- Any errors

### 2. Test New Implementation

```bash
# Edit configs/config-reasoning.yaml
# Change sql_retriever _type from:
#   _type: generate_sql_query_and_retrieve_tool
# To:
#   _type: vanna_sql_tool

# Restart NAT server
nat serve --config_file=configs/config-reasoning.yaml

# Run same test queries
```

Record same metrics for comparison.

## Evaluation Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Correctness** | 30% | Valid SQL generation, no syntax errors |
| **Accuracy** | 30% | Correct data returned matching expectations |
| **Performance** | 20% | Response time, vector search speed |
| **Reliability** | 10% | Error handling, edge case management |
| **Maintainability** | 10% | Code clarity, debugging ease, reusability |

## Results

### Query 1: Simple Count Query
*How many unique engines are in the FD001 training dataset?*

| Metric | sql_retriever_old | sql_retriever_vanna | Winner |
|--------|-------------------|---------------------|---------|
| SQL Generated | TBD | TBD | TBD |
| Correct Result? | TBD | TBD | TBD |
| Response Time | TBD | TBD | TBD |
| Errors | TBD | TBD | TBD |

### Query 2: Column Selection Query
*Retrieve time in cycles and operational setting 1 from FD001 test for unit 1*

| Metric | sql_retriever_old | sql_retriever_vanna | Winner |
|--------|-------------------|---------------------|---------|
| SQL Generated | TBD | TBD | TBD |
| Correct Result? | TBD | TBD | TBD |
| Response Time | TBD | TBD | TBD |
| Errors | TBD | TBD | TBD |

### Query 3: Aggregation Query
*What is the maximum sensor 2 value in the FD001 training dataset?*

| Metric | sql_retriever_old | sql_retriever_vanna | Winner |
|--------|-------------------|---------------------|---------|
| SQL Generated | TBD | TBD | TBD |
| Correct Result? | TBD | TBD | TBD |
| Response Time | TBD | TBD | TBD |
| Errors | TBD | TBD | TBD |

### Query 4: Filter and Column Query
*Get sensor 4 measurements for engine 5 in FD001 train dataset*

| Metric | sql_retriever_old | sql_retriever_vanna | Winner |
|--------|-------------------|---------------------|---------|
| SQL Generated | TBD | TBD | TBD |
| Correct Result? | TBD | TBD | TBD |
| Response Time | TBD | TBD | TBD |
| Errors | TBD | TBD | TBD |

### Query 5: RUL Retrieval Query
*Retrieve real RUL of each unit in FD001 test dataset*

| Metric | sql_retriever_old | sql_retriever_vanna | Winner |
|--------|-------------------|---------------------|---------|
| SQL Generated | TBD | TBD | TBD |
| Correct Result? | TBD | TBD | TBD |
| Response Time | TBD | TBD | TBD |
| Errors | TBD | TBD | TBD |

## Summary Score

| Criterion | sql_retriever_old | sql_retriever_vanna | Notes |
|-----------|-------------------|---------------------|-------|
| Correctness (30%) | TBD/30 | TBD/30 | TBD |
| Accuracy (30%) | TBD/30 | TBD/30 | TBD |
| Performance (20%) | TBD/20 | TBD/20 | TBD |
| Reliability (10%) | TBD/10 | TBD/10 | TBD |
| Maintainability (10%) | TBD/10 | TBD/10 | TBD |
| **TOTAL (100%)** | **TBD/100** | **TBD/100** | TBD |

## Decision

**Winner:** TBD

**Reasoning:** TBD

## Cleanup Steps

### If sql_retriever_vanna Wins

1. Delete old implementation:
   ```bash
   rm -rf src/nat_alm_agent/retrievers/
   ```

2. Update `src/nat_alm_agent/register.py`:
   ```python
   # Remove:
   # from .retrievers import generate_sql_query_and_retrieve_tool
   ```

3. Update config to use only vanna_sql_tool:
   ```yaml
   functions:
     sql_retriever:  # Single tool
       _type: vanna_sql_tool
       ...
   ```

4. Remove from dependencies if needed

### If sql_retriever_old Wins

1. Uninstall nat_vanna_tool:
   ```bash
   uv pip uninstall nat_vanna_tool
   ```

2. Remove package directory:
   ```bash
   rm -rf ../../packages/nat_vanna_tool/
   ```

3. Update `pyproject.toml`:
   ```toml
   # Remove nat_vanna_tool from dependencies
   # Remove from [tool.uv.sources]
   ```

4. Update config:
   ```yaml
   functions:
     sql_retriever:  # Single tool
       _type: generate_sql_query_and_retrieve_tool
       ...
   ```

## Lessons Learned

TBD - Document key insights from the comparison process

## References

- Test comparison suite: `tests/test_sql_comparison.py`
- Comparison summary: `test_comparison_output/COMPARISON_SUMMARY.md`
- Comparison report: `test_comparison_output/comparison_report.json`
