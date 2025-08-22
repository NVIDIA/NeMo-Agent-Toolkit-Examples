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

# EXAMPLE_TITLE

<!-- Replace with a brief description of what your example demonstrates -->
This example demonstrates [DESCRIPTION_OF_WHAT_YOUR_EXAMPLE_DOES] using the NVIDIA NeMo Agent toolkit, fully configured through a YAML file. It showcases [SPECIFIC_FEATURES_YOUR_EXAMPLE_HIGHLIGHTS].

## Table of Contents

- [EXAMPLE\_TITLE](#example_title)
  - [Table of Contents](#table-of-contents)
  - [Key Features](#key-features)
  - [Installation and Setup](#installation-and-setup)
    - [Install this Workflow:](#install-this-workflow)
    - [Set Up API Keys](#set-up-api-keys)
    - [Run the Workflow](#run-the-workflow)
  - [Deployment-Oriented Setup](#deployment-oriented-setup)
    - [Build the Docker Image](#build-the-docker-image)
    - [Run the Docker Container](#run-the-docker-container)
    - [Test the API](#test-the-api)
    - [Expected API Output](#expected-api-output)
  - [Customization Guide](#customization-guide)
    - [Adding New Functions](#adding-new-functions)
    - [Modifying the Agent](#modifying-the-agent)
    - [Using Different Models](#using-different-models)

---

## Key Features

<!-- Replace with your specific features -->
- **Custom Functions:** Demonstrates [DESCRIBE_YOUR_CUSTOM_FUNCTIONS]
- **Agent Integration:** Uses a [AGENT_TYPE] that [DESCRIBE_WHAT_THE_AGENT_DOES]
- **Multi-step Problem Solving:** Shows how an agent can [DESCRIBE_COMPLEX_WORKFLOWS]
- **Custom Function Registration:** Demonstrates the NeMo Agent toolkit plugin system for [DESCRIBE_PLUGIN_FUNCTIONALITY]
- **YAML-based Configuration:** Fully configurable workflow that showcases [DESCRIBE_CONFIGURATION_BENEFITS]

---

## Installation and Setup

### Install this Workflow:

From the root directory of the NeMo Agent toolkit library, run the following commands:

```bash
uv pip install -e examples/EXAMPLE_CATEGORY/EXAMPLE_NAME
```

### Set Up API Keys
Depending on which workflows you are running, you may need to obtain API keys from the respective services. Most NeMo Agent toolkit workflows require an NVIDIA API key defined with the `NVIDIA_API_KEY` environment variable. An API key can be obtained by visiting [`build.nvidia.com`](https://build.nvidia.com/) and creating an account.

Some workflows may also require an OpenAI API key. Visit [OpenAI](https://openai.com/) and create an account. Navigate to your account settings to obtain your OpenAI API key.

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
export OPENAI_API_KEY=<YOUR_API_KEY>  # OPTIONAL
```

### Run the Workflow

Return to your original terminal, and run the following command from the root of the NeMo Agent toolkit repo to execute this workflow with the specified input:

```bash
nat run --config_file examples/EXAMPLE_CATEGORY/EXAMPLE_NAME/configs/config.yml --input "YOUR_EXAMPLE_INPUT_PROMPT"
```

**Expected Workflow Output**
<!-- Replace with your expected output -->
```
YOUR_EXPECTED_OUTPUT_HERE
```

## Deployment-Oriented Setup

For a production deployment, use Docker:

### Build the Docker Image

Prior to building the Docker image ensure that you have followed the steps in the [Installation and Setup](#installation-and-setup) section, and you are currently in the NeMo Agent toolkit virtual environment.

From the root directory of the NeMo Agent toolkit repository, build the Docker image:

```bash
docker build --build-arg NAT_VERSION=$(python -m setuptools_scm) -t EXAMPLE_NAME -f examples/EXAMPLE_CATEGORY/EXAMPLE_NAME/Dockerfile .
```

### Run the Docker Container
Deploy the container:

```bash
docker run -p 8000:8000 -p 6006:6006 -e NVIDIA_API_KEY -e OPENAI_API_KEY EXAMPLE_NAME
```

Note, a phoenix telemetry service will be exposed at port 6006.

### Test the API
Use the following curl command to test the deployed API:

```bash
curl -X 'POST' \
  'http://localhost:8000/generate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"input_message": "YOUR_EXAMPLE_INPUT_PROMPT"}'
```

### Expected API Output
The API response should be similar to the following:

```bash
{
  "input": "YOUR_EXAMPLE_INPUT_PROMPT",
  "value": "YOUR_EXPECTED_OUTPUT_HERE"
}
```

## Customization Guide

<!-- Add any specific customization instructions for your example -->

### Adding New Functions
1. Define a new config class in `register.py` that inherits from `FunctionBaseConfig`
2. Create a function decorated with `@register_function`
3. Add the function to your `config.yml` file
4. Update the workflow's `tool_names` list

### Modifying the Agent
- Change the `_type` in the workflow section to use different agent types
- Adjust `max_iterations`, `temperature`, or other parameters as needed
- Add custom system prompts or modify the agent behavior

### Using Different Models
- Update the `model_name` in the LLM configuration
- Adjust parameters such as `temperature` and `max_tokens`
- Switch between different LLM providers (OpenAI, NIM, and so on)
