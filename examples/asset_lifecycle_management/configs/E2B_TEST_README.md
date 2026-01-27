# E2B Code Execution Test Setup

This guide helps you test the E2B cloud sandbox implementation without running the full ALM workflow.

## Prerequisites

1. **E2B API Key**
   - Sign up at https://e2b.dev/auth/sign-up
   - Get your API key from https://e2b.dev/dashboard
   - Free tier available for testing

2. **Install E2B Dependencies**
   ```bash
   cd examples/asset_lifecycle_management
   uv pip install -e ".[e2b]"
   ```

3. **Set Environment Variables**
   ```bash
   export E2B_API_KEY="your-e2b-api-key-here"
   export NVIDIA_API_KEY="your-nvidia-api-key"  # For LLM
   ```

4. **Prepare Workspace**
   ```bash
   # Ensure output_data directory exists
   mkdir -p output_data

   # Copy utilities if testing utils import
   cp -r utils_template output_data/utils
   ```

## Test Cases

### Test 1: Simple Code Execution

```bash
nat run --config_file configs/config-e2b-test.yaml \
  --input "Generate Python code to print 'Hello from E2B!'"
```

**Expected**: Should execute code in E2B cloud and return output.

### Test 2: File Generation

```bash
nat run --config_file configs/config-e2b-test.yaml \
  --input "Create a JSON file named 'test.json' with content {'message': 'E2B works!'}"
```

**Expected**:
- File created in E2B sandbox
- File downloaded to `output_data/test.json`
- Success message returned

### Test 3: Data Processing

```bash
nat run --config_file configs/config-e2b-test.yaml \
  --input "Create a pandas DataFrame with 5 random numbers, calculate their sum, and save to results.json"
```

**Expected**:
- DataFrame created and processed
- `results.json` downloaded to `output_data/`
- Sum displayed in output

### Test 4: Plotting

```bash
nat run --config_file configs/config-e2b-test.yaml \
  --input "Create a simple line plot of y=x^2 for x from 0 to 10 and save as plot.html"
```

**Expected**:
- Plot generated in E2B
- `plot.html` downloaded to `output_data/`
- Plot viewable in browser

### Test 5: Utils Import (Optional)

Only run if you have utils set up:

```bash
nat run --config_file configs/config-e2b-test.yaml \
  --input "Import utils and call utils.show_utilities() to list available functions"
```

**Expected**:
- Utils successfully imported from E2B sandbox
- Utility functions listed in output

## Troubleshooting

### Error: "E2B SDK not installed"
```bash
uv pip install e2b-code-interpreter
```

### Error: "E2B API key not set"
```bash
export E2B_API_KEY="your-key-here"
echo $E2B_API_KEY  # Verify it's set
```

### Error: "workspace_files_dir not found"
```bash
mkdir -p output_data
```

### Files not downloading
- Check E2B dashboard for quota limits
- Verify file extensions in `e2b_sandbox.py` (currently: .json, .html, .png, .jpg, .csv, .pdf)
- Check E2B sandbox logs for file creation

## Comparison with Local Docker

| Feature | Local Docker | E2B Cloud |
|---------|-------------|-----------|
| Setup | Requires Docker + container | Just API key |
| Speed (cold start) | ~2-5 seconds | ~150ms |
| Speed (execution) | Fast | + file transfer overhead |
| File access | Mounted volume | Upload/download |
| Database | Direct access | Must upload |
| Cost | Free (local resources) | API usage based |
| Network | Not required | Required |

## Next Steps

After successful testing:

1. **Compare Performance**
   - Measure execution times
   - Test with larger files/databases
   - Check reliability over multiple runs

2. **Integration Testing**
   - Test with full ALM workflow
   - Update `config-reasoning.yaml` to use E2B
   - Compare results with local Docker

3. **Documentation**
   - Update main README with E2B option
   - Add to CLAUDE.md as alternative implementation
   - Document decision criteria

## Configuration Reference

See `config-e2b-test.yaml` for the minimal configuration structure:

```yaml
functions:
  e2b_code_execution:
    _type: e2b_code_execution
    e2b_api_key: "${E2B_API_KEY}"
    workspace_files_dir: "output_data"
    timeout: 30.0
    max_output_characters: 2000

  code_generation_assistant:
    _type: code_generation_assistant
    llm_name: "coding_llm"
    code_execution_tool: "e2b_code_execution"  # Points to E2B
    output_folder: "output_data"
```

## Support

- E2B Documentation: https://e2b.dev/docs
- E2B Discord: https://discord.gg/U7KEcGErtQ
- GitHub Issues: https://github.com/NVIDIA/NeMo-Agent-Toolkit-Examples/issues
