# Data Directory

This directory is for storing any data files needed to run your example.

Examples of files you might place here:
- Sample input data (JSON, CSV, text files, and so on)
- Test datasets
- Configuration data
- Reference files

## Usage

Reference data files in your functions using relative paths from the example root:
```python
import importlib.resources

data_file: Path = importlib.resources.files("nat_EXAMPLE_NAME").joinpath("data", "sample_data.json").absolute()
```

Or use the data directory in your configuration files by referencing the appropriate paths.
