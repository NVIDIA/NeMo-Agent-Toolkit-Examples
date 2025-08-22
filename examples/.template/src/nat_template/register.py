# SPDX-FileCopyrightText: Copyright (c) 2024-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

import logging

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


# Example function configuration class
class ExampleFunctionConfig(FunctionBaseConfig, name="example_function"):
    """
    Configuration class for the example function.

    Add any configuration parameters your function needs here.
    For example:
    - parameter1: str = "default_value"
    - parameter2: int = 42
    """
    pass


@register_function(config_type=ExampleFunctionConfig)
async def example_function(tool_config: ExampleFunctionConfig, builder: Builder):
    """
    Example function template.

    Replace this with your actual function implementation.
    This function should:
    1. Define the actual function logic (async def _example_function)
    2. Return a FunctionInfo object that describes the function

    Args:
        tool_config: Configuration for this function
        builder: Builder instance for accessing other components

    Yields:
        FunctionInfo: Information about the function for the agent to use
    """

    async def _example_function(input_text: str) -> str:
        """
        Your actual function implementation goes here.

        Args:
            input_text: Input from the agent

        Returns:
            str: Result of the function
        """
        # TODO: Replace with your actual function logic
        return f"Example function processed: {input_text}"

    # Create a Generic NAT tool that can be used with any supported LLM framework
    yield FunctionInfo.from_fn(_example_function,
                               description=("This is an example function template. "
                                            "Replace this description with what your function actually does."))


# Add more functions as needed following the same pattern:
# 1. Create a config class that inherits from FunctionBaseConfig
# 2. Create a function decorated with @register_function
# 3. Implement the actual function logic
# 4. Yield a FunctionInfo object
