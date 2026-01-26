# Migration to NeMo-Agent-Toolkit-Examples

**Date:** January 25, 2026
**Status:** ✅ Migration Complete, Ready for Comparison Testing

## Overview

The Asset Lifecycle Management (ALM) Agent has been successfully migrated from `GenerativeAIExamples` to `NeMo-Agent-Toolkit-Examples` repository with the following enhancements:

1. **Standalone Vanna SQL Tool Package** - Reusable SQL generation tool (`nat_vanna_tool`)
2. **Dual SQL Implementation** - Both old and new implementations available for comparison
3. **Improved Package Structure** - Following NAT best practices
4. **Fixed Hardcoded Paths** - All paths now use relative references or environment variables

## Repository Structure

```
NeMo-Agent-Toolkit-Examples/
├── packages/
│   └── nat_vanna_tool/              # NEW: Standalone SQL tool package
│       ├── src/nat_vanna_tool/
│       │   ├── vanna_sql_tool.py    # Main @register_function tool
│       │   ├── vanna_manager.py     # Singleton manager
│       │   ├── vanna_client.py      # NIMVanna, ElasticNIMVanna
│       │   ├── config_schemas.py    # Configuration models
│       │   └── register.py          # NAT entry point
│       ├── pyproject.toml
│       └── README.md
│
└── industries/
    └── asset_lifecycle_management/  # MIGRATED: ALM Agent
        ├── src/nat_alm_agent/
        │   ├── retrievers/          # PRESERVED: Original SQL implementation
        │   ├── predictors/
        │   ├── plotting/
        │   └── evaluators/
        ├── configs/
        │   └── config-reasoning.yaml  # UPDATED: Dual SQL tool config
        ├── database/                # Existing ChromaDB for old tool
        ├── database_vanna/          # NEW: Separate ChromaDB for new tool
        ├── tests/
        │   └── test_sql_comparison.py  # NEW: Comparison test suite
        ├── COMPARISON.md            # NEW: Comparison testing documentation
        └── pyproject.toml           # UPDATED: Added nat_vanna_tool dependency
```

## What Changed

### 1. Package Names
- `asset_lifecycle_management_agent` → `nat_alm_agent`
- Entry point: `nat_alm_agent.register`

### 2. Dependencies
Added to `pyproject.toml`:
```toml
dependencies = [
  "nvidia-nat[profiling, langchain, telemetry]>=1.3.0",
  "nat_vanna_tool",  # NEW: Standalone Vanna tool
  # ... other deps
]

[tool.uv.sources]
nat_vanna_tool = { path = "../../packages/nat_vanna_tool", editable = true }
momentfm = { path = "./moment", editable = true }
```

### 3. SQL Tool Configuration

The config file now includes **both** SQL implementations:

```yaml
functions:
  # Original implementation (preserved for comparison)
  sql_retriever_old:
    _type: generate_sql_query_and_retrieve_tool
    vector_store_path: "database"
    ...

  # New package-based implementation
  sql_retriever_vanna:
    _type: vanna_sql_tool
    vector_store_path: "database_vanna"
    ...

  # Active tool (currently uses old implementation)
  sql_retriever:
    _type: generate_sql_query_and_retrieve_tool
    ...
```

To switch implementations, change `sql_retriever`'s `_type` to `vanna_sql_tool`.

### 4. Path Fixes
- Removed hardcoded paths like `/Users/vikalluru/Documents/GenerativeAIExamples/...`
- Updated to use `os.getcwd()` and relative paths
- Config prompts now reference `output_data/` instead of absolute paths

## Installation

### Using alm Conda Environment

```bash
# Activate environment
conda activate alm

# Install Vanna Tool package
cd ~/Documents/NeMo-Agent-Toolkit-Examples/packages/nat_vanna_tool
uv pip install -e .

# Install ALM Agent
cd ~/Documents/NeMo-Agent-Toolkit-Examples/industries/asset_lifecycle_management
uv pip install -e .
```

### Verify Installation

```bash
# Test imports
python -c "from nat_vanna_tool import vanna_sql_tool; print('✓ Vanna tool OK')"
python -c "from nat_alm_agent.retrievers import generate_sql_query_and_retrieve_tool; print('✓ ALM agent OK')"
```

## Comparison Testing

### Why Two Implementations?

We preserved both SQL tools to:
1. **Compare Performance** - Which generates better SQL?
2. **Test Accuracy** - Which retrieves correct data?
3. **Measure Speed** - Response time comparison
4. **Validate Approach** - Package vs embedded implementation
5. **Choose Winner** - Delete the inferior tool after testing

### Running Comparison Tests

```bash
# 1. Activate environment
conda activate alm
cd ~/Documents/NeMo-Agent-Toolkit-Examples/industries/asset_lifecycle_management

# 2. Run basic import tests
pytest tests/test_sql_comparison.py::TestSQLComparison::test_import_both_tools -v

# 3. Generate comparison report framework
pytest tests/test_sql_comparison.py::TestSQLComparison::test_generate_comparison_report -v

# 4. View manual testing instructions
pytest tests/test_sql_comparison.py::test_manual_comparison_instructions -v -s
```

### Manual Comparison Process

See [`COMPARISON.md`](COMPARISON.md) for detailed testing instructions including:
- Test queries to run
- Metrics to collect
- Evaluation criteria
- Decision framework
- Cleanup steps for winner/loser

## Migration Checklist

- [x] Clone NeMo-Agent-Toolkit-Examples repository
- [x] Create nat_vanna_tool package structure
- [x] Port Vanna implementation to standalone package
- [x] Create package pyproject.toml and README
- [x] Copy all ALM agent source files (including retrievers/)
- [x] Copy data, models, configs, scripts
- [x] Update ALM agent pyproject.toml
- [x] Update register.py with dual tool notes
- [x] Update config with both SQL tools
- [x] Fix all hardcoded paths
- [x] Set up MOMENT library as submodule
- [x] Install nat_vanna_tool package
- [x] Install ALM agent package
- [x] Verify database and vector stores
- [x] Create comparison test suite
- [ ] Run comparison tests (manual)
- [ ] Document results in COMPARISON.md
- [ ] Choose winning implementation
- [ ] Delete losing implementation
- [ ] Update README with final choice

## Key Files

| File | Description |
|------|-------------|
| `packages/nat_vanna_tool/` | Standalone Vanna SQL tool package |
| `COMPARISON.md` | Comparison testing documentation and results |
| `tests/test_sql_comparison.py` | Automated comparison test suite |
| `test_comparison_output/COMPARISON_SUMMARY.md` | Generated comparison summary |
| `configs/config-reasoning.yaml` | Updated config with dual SQL tools |
| `src/nat_alm_agent/register.py` | Tool registration with dual setup notes |

## Next Steps

1. **Run Manual Comparison Tests**
   - Test both SQL tools with sample queries
   - Measure performance and accuracy
   - Document results in COMPARISON.md

2. **Choose Winner**
   - Evaluate based on criteria in COMPARISON.md
   - Consider correctness, accuracy, performance, reliability, maintainability

3. **Cleanup**
   - Delete losing implementation
   - Update config to use only winner
   - Remove unused dependencies
   - Update documentation

4. **Final Validation**
   - Run end-to-end tests
   - Verify all features work
   - Update main README

## Environment Details

- **Python:** 3.12.12 (alm environment)
- **NAT Version:** 1.3.1
- **Vanna Version:** 0.7.9
- **ChromaDB:** Latest compatible version
- **Database:** SQLite (nasa_turbo.db)

## Migration Benefits

1. **Reusable Package** - nat_vanna_tool can be used in other NAT projects
2. **Better Organization** - Clear separation of concerns
3. **Comparison Testing** - Data-driven decision on best implementation
4. **No Breaking Changes** - Old implementation preserved until testing complete
5. **Improved Maintainability** - Fixed paths, better structure

## Troubleshooting

### Import Errors
```bash
# Ensure packages are installed in editable mode
cd packages/nat_vanna_tool && uv pip install -e .
cd industries/asset_lifecycle_management && uv pip install -e .
```

### Config Validation
```bash
# Validate config file
nat serve --config_file=configs/config-reasoning.yaml --validate
```

### Database Issues
```bash
# Check database tables
python -c "import sqlite3; conn = sqlite3.connect('database/nasa_turbo.db');
cursor = conn.cursor(); cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"');
print([t[0] for t in cursor.fetchall()]); conn.close()"
```

## References

- Original Location: `GenerativeAIExamples/industries/asset_lifecycle_management_agent/`
- New Location: `NeMo-Agent-Toolkit-Examples/industries/asset_lifecycle_management/`
- Vanna Tool Package: `NeMo-Agent-Toolkit-Examples/packages/nat_vanna_tool/`
- Comparison Results: [`COMPARISON.md`](COMPARISON.md)
- Test Suite: [`tests/test_sql_comparison.py`](tests/test_sql_comparison.py)
