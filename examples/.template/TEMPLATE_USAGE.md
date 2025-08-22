# NVIDIA NeMo Agent Toolkit Example Template

This directory serves as a template for creating new examples in the NeMo Agent toolkit. It follows the required structure and includes all necessary files with placeholder content.

## Template Structure

The template follows this exact structure as required:

```
examples/
  .template/           # Template directory (use any name for your actual example)
    configs/          # Symlink to `src/nat_EXAMPLE_NAME/configs/` ✓
    data/            # [Optional] Symlink to `src/nat_EXAMPLE_NAME/data/` ✓
    scripts/         # [Optional] Directory for scripts needed to setup the example ✓
    src/
      nat_EXAMPLE_NAME/  # All example modules must start with the prefix `nat_` ✓
        configs/
          config.yml  # At least one config file for the example ✓
        data/         # [Optional] Data files for the example ✓
        __init__.py   # ✓
        register.py   # ✓
    README.md        # Documentation for the example ✓
    pyproject.toml   # Must register the example with `nat` ✓
```

## How to Use This Template

### 1. Copy the Template
```bash
# From the NeMo Agent toolkit root directory
cp -r examples/.template examples/YOUR_CATEGORY/YOUR_EXAMPLE_NAME
```

### 2. Replace Placeholder Names
Replace all instances of the following placeholders with your actual values:

**Directory/File Names:**
- `.template` → `YOUR_EXAMPLE_NAME`
- `nat_template` → `nat_YOUR_EXAMPLE_NAME`

**File Content Placeholders:**
- `EXAMPLE_NAME` → Your actual example name
- `EXAMPLE_TITLE` → Your example title for documentation
- `EXAMPLE_DESCRIPTION` → Brief description of your example
- `EXAMPLE_CATEGORY` → The category subdirectory (such as getting_started, agents, and so on)
- `YOUR_EXAMPLE_INPUT_PROMPT` → Example input for your workflow
- `YOUR_EXPECTED_OUTPUT_HERE` → Expected output from your workflow

### 3. Update Core Files

#### pyproject.toml
- Update `name` field: `"nat_YOUR_EXAMPLE_NAME"`
- Update `description` field with your example description
- Update entry point: `nat_YOUR_EXAMPLE_NAME = "nat_YOUR_EXAMPLE_NAME.register"`
- Adjust dependencies if needed

#### register.py
- Replace `ExampleFunctionConfig` with your actual function config classes
- Implement your actual functions instead of the example template
- Update function descriptions and logic

#### config.yml
- Update the `functions` section with your actual function names
- Configure the appropriate LLM settings for your use case
- Set up the workflow type and parameters that fit your example

#### README.md
- Replace all placeholder content with your actual documentation
- Update installation paths and example commands
- Provide real expected output examples
- Add any specific setup instructions for your example

### 4. Update the Symlinks
```bash
cd examples/YOUR_CATEGORY/YOUR_EXAMPLE_NAME
rm configs data
ln -s src/nat_YOUR_EXAMPLE_NAME/configs configs
ln -s src/nat_YOUR_EXAMPLE_NAME/data data
```

### 5. Customize Optional Directories

#### data/
- Add your actual data files to `src/nat_YOUR_EXAMPLE_NAME/data/`
- Update or remove the README.md as appropriate
- Reference data files correctly in your functions (they will be accessible through the symlink)

#### scripts/
- Create actual setup scripts if needed
- Update setup.sh with real setup logic
- Make scripts executable: `chmod +x scripts/*.sh`

### 6. Test Your Example

1. Install your example:
   ```bash
   uv pip install -e examples/YOUR_CATEGORY/YOUR_EXAMPLE_NAME
   ```

2. Run your workflow:
   ```bash
   nat run --config_file examples/YOUR_CATEGORY/YOUR_EXAMPLE_NAME/configs/config.yml --input "Your test input"
   ```

## Template Files Explained

### Required Files

- **pyproject.toml**: Python project configuration that registers your example with NAT
- **README.md**: Documentation for users of your example
- **src/nat_EXAMPLE_NAME/__init__.py**: Python module initialization (usually empty)
- **src/nat_EXAMPLE_NAME/register.py**: Function registration and implementation
- **src/nat_EXAMPLE_NAME/configs/config.yml**: Workflow configuration
- **configs**: Symlink to the configs directory for easy access
- **data**: Symlink to the data directory for easy access

### Optional Files

- **src/nat_EXAMPLE_NAME/data/**: Any data files your example needs
- **scripts/**: Setup or utility scripts
- **Dockerfile**: For containerized deployment (not included in template, add if needed)
- **tests/**: Test files (not included in template, add if needed)

## Best Practices

1. **Naming Convention**: Always prefix your module with `nat_`
2. **Documentation**: Provide clear examples and expected outputs
3. **Configuration**: Use descriptive function and parameter names
4. **Error Handling**: Include proper validation in your functions
5. **Dependencies**: Only add dependencies that are actually needed
6. **Testing**: Consider adding tests for your functions

## Example Categories

Place your example in the appropriate category directory:
- `getting_started/`: Simple introductory examples
- `agents/`: Agent-specific examples
- `custom_functions/`: Examples focused on custom function development
- `frameworks/`: Integration with other frameworks
- `evaluation_and_profiling/`: Examples with evaluation metrics
- And more... (see the examples directory for all categories)

## Naming Conventions

### Module Naming
- **Full name on first use**: "NVIDIA NeMo Agent toolkit"
- **Subsequent references**: "NeMo Agent toolkit"
- **Abbreviations**: "NAT" or "nat"
  - "nat" for the API namespace and CLI tool
  - "nvidia-nat" for the package name
  - "NAT" for environment variable prefixes and informal usage in comments

### Template Placeholders
- Use `EXAMPLE_NAME` in ALL_CAPS for placeholders that should be replaced
- Use `YOUR_EXAMPLE_NAME` for user-specific naming
- Use `EXAMPLE_CATEGORY` for directory categorization

### Deprecated Names
Never use these deprecated names in new examples:
- Agent Intelligence toolkit
- aiqtoolkit
- AgentIQ
- AIQ/aiq

Always use the current NeMo Agent toolkit naming convention.

## Support

For questions about creating examples, refer to:
- The existing examples in the examples/ directory
- The NeMo Agent toolkit documentation
- The project's CONTRIBUTING.md file
