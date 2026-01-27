# Asset Lifecycle Management (ALM) - Session Notes

This file contains session-specific notes for working with the ALM example.

## Current Session (2026-01-26)

### E2B Cloud Sandbox Setup ✅ COMPLETE

**Goal:** Set up and test E2B cloud sandbox as an alternative to local Docker for code execution.

**Status:** ✅ E2B integration is fully working! Code executes in cloud, files download successfully.

**Completed Steps:**

1. **API Key Configuration**
   - E2B API Key added to `~/.zshrc`: `export E2B_API_KEY="e2b_87798e37413e2ab60ecf20d7fa1fd797177e2582"`
   - NVIDIA API Key added to `~/.zshrc`: `export NVIDIA_API_KEY="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"`
   - Keys are automatically loaded in all new terminal sessions

2. **E2B SDK Installation**
   ```bash
   conda activate alm
   uv pip install "e2b-code-interpreter>=0.2.0"
   ```
   - Installed E2B SDK v2.4.1
   - Located in: `/opt/homebrew/anaconda3/envs/alm/lib/python3.12/site-packages/e2b/`

3. **SSL Certificate Updates (macOS)**
   ```bash
   # Updated via conda
   conda install -y ca-certificates  # 2025.11.4 → 2025.12.2
   conda install -y openssl

   # Updated via uv
   uv pip install --upgrade certifi  # 2025.11.12 → 2026.1.4
   ```
   - Added to `~/.zshrc`:
     ```bash
     export SSL_CERT_FILE="/opt/homebrew/anaconda3/etc/ssl/cert.pem"
     export REQUESTS_CA_BUNDLE="/opt/homebrew/anaconda3/etc/ssl/cert.pem"
     ```

4. **Test Script**
   - Location: `test_e2b_sandbox.py`
   - Tests 4 scenarios: simple execution, file generation, data processing, utils upload

### Current Issue: SSL Certificate Verification

**Error:** `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1010)`

**Root Cause:**
- macOS-specific SSL issue with Python's httpx library (used by E2B SDK)
- System curl works fine (returns 401 as expected), but Python SSL doesn't trust E2B API certificates
- Environment variables (`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`) are not being respected by httpx

**What We Tried:**
1. ✅ Upgraded conda ca-certificates
2. ✅ Upgraded certifi via uv
3. ✅ Set SSL_CERT_FILE environment variable
4. ✅ Set REQUESTS_CA_BUNDLE environment variable
5. ❌ Issue persists - httpx doesn't use these environment variables

**Test Command:**
```bash
source /opt/homebrew/anaconda3/etc/profile.d/conda.sh
conda activate alm
export E2B_API_KEY="e2b_87798e37413e2ab60ecf20d7fa1fd797177e2582"
python test_e2b_sandbox.py
```

### Next Steps to Try

**Option 1: Python Certificate Installer (macOS Official)**
```bash
# Find Python installation
ls /Applications/ | grep Python

# Run certificate installer (if exists)
/Applications/Python\ 3.12/Install\ Certificates.command
```

**Option 2: Test on Linux/Docker**
- The E2B integration code is correct
- SSL issues are macOS-specific
- Would work fine on Linux servers, Docker containers, CI/CD environments

**Option 3: Use Local Docker Sandbox (Default)**
- ALM example defaults to local Docker sandbox
- E2B is an optional cloud alternative
- Local Docker doesn't have SSL certificate issues
- Command to start:
  ```bash
  cd /path/to/NeMo-Agent-Toolkit/src/nat/tool/code_execution/
  ./local_sandbox/start_local_sandbox.sh local-sandbox /path/to/output_data/
  ```

**Option 4: Temporarily Disable SSL Verification (Testing Only - NOT for Production)**
```python
# Modify e2b_sandbox.py temporarily
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

### Files Modified This Session

1. **~/.zshrc**
   - Added E2B_API_KEY
   - Added SSL_CERT_FILE and REQUESTS_CA_BUNDLE environment variables

2. **pyproject.toml**
   - Changed `nat_vanna_tool` → `nvidia_nat_vanna`
   - Added `e2b = ["e2b-code-interpreter>=0.2.0"]` optional dependency

3. **Existing E2B Implementation Files** (already committed):
   - `src/nat_alm_agent/code_execution/e2b_sandbox.py`
   - `src/nat_alm_agent/code_execution/e2b_code_execution_tool.py`
   - `test_e2b_sandbox.py`
   - `configs/config-e2b-test.yaml`

### Environment Details

**Conda Environment:** `alm`
- Python: 3.12.12
- Location: `/opt/homebrew/anaconda3/envs/alm`

**Key Packages:**
- e2b: 2.11.0
- e2b-code-interpreter: 2.4.1
- certifi: 2026.1.4
- ca-certificates: 2025.12.2

**Homebrew Anaconda:**
- Location: `/opt/homebrew/anaconda3`
- Conda init in `~/.zshrc` (lines 185-198)

### Documentation References

- **E2B Test Guide:** `configs/E2B_TEST_README.md`
- **SSL Setup Guide:** `configs/SSL_CERTIFICATE_SETUP.md`
- **E2B Sandbox Implementation:** `src/nat_alm_agent/code_execution/e2b_sandbox.py`
- **E2B Config Example:** `configs/config-e2b-test.yaml`
- **Main CLAUDE.md:** `/Users/vikalluru/Documents/NeMo-Agent-Toolkit-Examples/CLAUDE.md`
- **Examples CLAUDE.md:** `/Users/vikalluru/Documents/NeMo-Agent-Toolkit-Examples/examples/CLAUDE.md`

### Resume Instructions

When resuming this session:

1. **Load environment:**
   ```bash
   cd /Users/vikalluru/Documents/NeMo-Agent-Toolkit-Examples/examples/asset_lifecycle_management
   source /opt/homebrew/anaconda3/etc/profile.d/conda.sh
   conda activate alm
   ```

2. **Verify E2B API key:**
   ```bash
   echo $E2B_API_KEY  # Should show: e2b_87798e37413e2ab60ecf20d7fa1fd797177e2582
   ```

3. **Test E2B (if SSL fixed):**
   ```bash
   python test_e2b_sandbox.py
   ```

4. **Other features to explore:**
   - ⏳ **TODO: Test local Docker sandbox with new code execution changes** - The code_generation_assistant was updated to work with E2B. Should verify it still works correctly with local Docker sandbox.
   - Run full ALM workflow with production config
   - SQL retriever comparison moved to `new_sql_tool_exploration/` (deferred)

### Known Issues

1. **SSL Certificate Verification on macOS**
   - Affects E2B cloud sandbox only
   - Local Docker sandbox works fine
   - Not an issue on Linux/CI environments

2. **Dual SQL Implementations**
   - Currently comparing old (generate_sql_query_and_retrieve_tool) vs new (vanna_sql_tool from nvidia_nat_vanna)
   - Both are available, old is default
   - See `configs/config-sql-comparison-old.yaml` and `configs/config-sql-comparison-new.yaml`

3. **Git Commit Guidelines**
   - All commits must be GPG-signed: `git commit -S`
   - Do NOT include "Co-Authored-By: Claude" in commit messages
   - Exclude markdown files except README.md and CLAUDE.md
   - Exclude data folders and database files (already in .gitignore)

### Session Summary (2026-01-26)

**Major Accomplishments:**
1. ✅ **E2B Cloud Sandbox Integration** - Fully working end-to-end
   - Fixed async/await issues in `code_generation_assistant.py`
   - Fixed stdout/stderr list-to-string conversion
   - Tested successfully with file generation task

2. ✅ **Package Cleanup**
   - Consolidated to single `nat_alm_agent` package name (shorter, cleaner)
   - Fixed MOMENT library numpy dependency conflict
   - Installed all dependencies successfully

3. ✅ **Repository Organization**
   - Moved SQL comparison files to `new_sql_tool_exploration/` (deferred)
   - Added `.gitignore` for exploration folder
   - Added E2B configuration comments to main config file
   - Kept only essential config files (config-reasoning.yaml, config-e2b-test.yaml)

**Files Modified:**
- `src/nat_alm_agent/plotting/code_generation_assistant.py` - Fixed E2B integration
- `configs/config-reasoning.yaml` - Added E2B configuration comments
- `moment/pyproject.toml` - Updated numpy constraint from `==1.26.2` to `>=1.26.2`
- `~/.zshrc` - Added NVIDIA_API_KEY
- `CLAUDE.md` - Updated session notes

**Files Moved to `new_sql_tool_exploration/`:**
- `configs/config-sql-comparison-new.yaml`
- `configs/config-sql-comparison-old.yaml`
- `SQL_COMPARISON_READY.md`
- `scripts/run_sql_comparison.py`
- `tests/test_sql_comparison.py`
- `setup_databricks_from_txt.py`
- `setup_databricks.py`
- `eval_data/eval_set_sql_only.json`

### Previous Session Notes

- Successfully committed and pushed E2B implementation and SQL comparison configs
- Removed hardcoded Databricks tokens from setup scripts
- Updated pyproject.toml with nvidia_nat_vanna package
