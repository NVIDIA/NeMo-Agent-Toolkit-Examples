<!--
SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->


# Contributing Guidelines

The NeMo Agent Toolkit Examples repository is a collection of examples that demonstrate how to use the NeMo Agent Toolkit. We welcome contributions from the community to add new examples, improve existing examples, and fix bugs.

To ensure your contribution is accepted, please follow the guidelines below.

## What to Contribute

### New Examples

If you have an idea for a new example, or would like to contribute an example you have created, please enture that your example follows these general guidelines:

1. Examples should demonstrate a specific use case or feature of the NeMo Agent Toolkit.
2. Examples should be unique and not already covered by an existing example.
   1. If your example is a variation of an existing example, consider updating the existing example instead of creating a new one.
3. Examples should be reliable and reproducible.
4. Examples should adhere to the [Example Requirements](#example-requirements) below.

If you are unsure about whether your example is a good fit for the repository, please open up an issue to discuss your idea before submitting a pull request.

### Example Updates

Examples can be updated to include new features, improve documentation, or fix bugs. If you are updating an example, please ensure that your changes follow these general guidelines:

1. Examples should be updated to reflect the latest version of the NeMo Agent Toolkit.
2. All new features should be documented and tested.
3. Examples should continue to adhere to the [Example Requirements](#example-requirements) below.

### Bug Fixes

If you have found a bug in an example, please open up an issue to report the bug or submit a pull request to fix the bug. Bug fixes do not need to update the example to reflect the latest version of the NeMo Agent Toolkit.

## Example Requirements

### Organization
Examples should follow a specified structure to maintain consistency across the repository. The recommended structure is:
```bash
examples/
  $EXAMPLE_NAME/
    configs/ # Symlink to `src/nat_$EXAMPLE_NAME/configs/`
    data/ # [Optional] Symlink to `src/nat_$EXAMPLE_NAME/data/`
    scripts/ # [Optional] Directory for scripts needed to setup the example
    src/
      nat_$EXAMPLE_NAME/ # All example modules must start with the prefix `nat_`
        configs/
          config.yml # At least one config file for the example
        data/ # [Optional] Directory for data files needed to run the example
          ... # [Optional] Data files needed to run the example
        __init__.py
        register.py
    README.md or README.ipynb # Documentation for the example
    pyproject.toml # Must register the example with `nat`
```

### Documentation
Each example must include clear documentation on how to run it. This can be provided in either:
- A README.md file at the top level of the example directory
- A README.ipynb Jupyter notebook that walks through the example

In both cases, the documentation should include:

- A description of the example
- Key features of the example
- Setup instructions
- How to run the example
- Expected results
- [Optional] Troubleshooting tips

## Testing
To ensure examples remain functional, each example must include unit tests written using `pytest`. Tests should verify the core functionality of the example and help catch issues when dependencies are updated.

## Code Style
All code should be compatible with the linting rules defined in the root `pyproject.toml` file. To ensure your code is compatible, run the following command:

```bash
# Ensure all development dependencies are installed
uv sync --dev

./ci/scripts/checks.sh
```

## License
All contributions must be made under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).

## Code of Conduct
All contributors must follow the [Code of Conduct](CODE-OF-CONDUCT.md).
