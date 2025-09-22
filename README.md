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

![NVIDIA NeMo Agent Toolkit Examples](./docs/source/_static/banner.png "NVIDIA NeMo Agent Toolkit Examples")

# NVIDIA NeMo Agent Toolkit Examples

This repository contains community examples for the [NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit). Whether you're new to using the toolkit, an experienced user looking for inspiration, or hoping to share your own examples with the community, this repository will help you get started.


> [!NOTE]
> Both the NeMo Agent Toolkit [repository](https://github.com/NVIDIA/NeMo-Agent-Toolkit) and this repository contain examples. However, there are some differences in the examples between the two repositories:
>
> | Repository | Example Focus | Update Cadence |
> |------------|--------------|----------------|
> | NeMo Agent Toolkit | Examples focused on toolkit features and capabilities | Updated each release to work with latest version |
> | NeMo Agent Toolkit Examples | Examples driven by community use cases and scenarios | Bound to specific toolkit versions, updated as needed |


## Getting Started

Each example is a self-contained directory that contains a README with instructions for running the example.

All examples require a local clone of this repository, uv, and a Python 3.11+ environment. Please follow the instructions below to get started.

1. Clone the repository

   ```bash
   git clone https://github.com/NVIDIA/NeMo-Agent-Toolkit-Examples.git
   cd NeMo-Agent-Toolkit-Examples
   ```

1. Fetch the data sets by downloading the LFS files.
   ```bash
   git lfs install
   git lfs fetch
   git lfs pull
   ```

1. Install uv using the instructions [here](https://docs.astral.sh/uv/getting-started/installation/).

1. Create a new environment using the following command:

   ```bash
   uv venv --python 3.13 --seed .venv
   source .venv/bin/activate

   uv sync --dev
   ```

   > [!NOTE]
   > Python 3.11 & 3.12 are also supported simply replace `3.13` with `3.11` or `3.12` in the `uv` command above.

To run an example, navigate to the example directory and follow the instructions in the README.

## Contributing

We welcome contributions to the repository! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for more information about how to contribute to the repository, requirements, and how to submit an example.
