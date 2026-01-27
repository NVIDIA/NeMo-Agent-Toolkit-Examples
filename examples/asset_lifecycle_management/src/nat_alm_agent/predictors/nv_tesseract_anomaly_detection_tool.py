# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

"""NV Tesseract-based anomaly detection tool using NVIDIA NIM."""

import json
from typing import Optional

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from pydantic import BaseModel, Field


class NVTesseractAnomalyDetectionToolConfig(FunctionBaseConfig, name="nv_tesseract_anomaly_detection"):
    """Configuration for NV Tesseract anomaly detection tool."""

    llm_name: str = Field(description="Name of the LLM to use for NV Tesseract NIM")
    model_name: str = Field(
        default="nvidia/nv-anomaly-tesseract-1.0",
        description="NIM model name for anomaly detection"
    )
    lookback_period: int = Field(
        default=30,
        description="Number of time steps to look back for anomaly detection"
    )
    forecast_horizon: int = Field(
        default=10,
        description="Number of time steps to forecast"
    )


class AnomalyDetectionInput(BaseModel):
    """Input schema for anomaly detection."""

    unit_number: int = Field(description="Unit number to analyze")
    dataset_name: str = Field(description="Dataset name (e.g., 'train_FD001', 'test_FD002')")


@register_function(config_type=NVTesseractAnomalyDetectionToolConfig)
async def nv_tesseract_anomaly_detection_tool(
    config: NVTesseractAnomalyDetectionToolConfig, builder: Builder
):
    """
    NV Tesseract-based anomaly detection using NVIDIA NIM.

    This tool uses NVIDIA's NV Tesseract foundation model for time-series anomaly detection.
    It analyzes sensor data from turbofan engines to identify anomalous patterns.
    """

    async def _detect_anomalies(unit_number: int, dataset_name: str) -> str:
        """
        Detect anomalies in sensor data using NV Tesseract NIM.

        Args:
            unit_number: Unit number to analyze
            dataset_name: Dataset name (e.g., 'train_FD001', 'test_FD002')

        Returns:
            JSON string containing anomaly detection results
        """
        # Get the LLM (NIM endpoint)
        llm = await builder.get_llm(config.llm_name)

        # Get SQL retriever to fetch sensor data
        sql_retriever = await builder.get_function("sql_retriever")

        # Query to fetch sensor data for the unit
        sensor_query = (
            f"Retrieve all sensor readings for unit {unit_number} from {dataset_name} dataset. "
            f"Include all sensor columns (sensor_1 through sensor_21) and the time_in_cycles column."
        )

        # Fetch data using SQL retriever
        sql_result = await sql_retriever.ainvoke({"query": sensor_query})

        if not sql_result or "error" in sql_result.lower():
            return json.dumps({
                "error": f"Failed to retrieve sensor data for unit {unit_number}",
                "details": sql_result
            })

        # Parse the SQL result to extract sensor data
        try:
            # The SQL retriever returns a string, parse it to get the data
            if isinstance(sql_result, str):
                # Try to extract data from the result string
                # The format is typically a table or JSON
                data_lines = sql_result.strip().split('\n')

                # Skip header and parse data
                sensor_values = []
                for line in data_lines[1:]:  # Skip header
                    if line.strip():
                        # Extract numeric values
                        values = [float(v) for v in line.split() if v.replace('.', '').replace('-', '').isdigit()]
                        if values:
                            sensor_values.append(values)

                if not sensor_values:
                    return json.dumps({
                        "error": "No valid sensor data found",
                        "raw_result": sql_result
                    })

                # Prepare data for NV Tesseract
                # Take the last lookback_period points for analysis
                lookback_data = sensor_values[-config.lookback_period:] if len(sensor_values) >= config.lookback_period else sensor_values

                # Format prompt for NV Tesseract NIM
                prompt = f"""Analyze the following time-series sensor data for anomalies:

Dataset: {dataset_name}
Unit: {unit_number}
Lookback Period: {config.lookback_period} time steps
Forecast Horizon: {config.forecast_horizon} time steps

Sensor Data (most recent {len(lookback_data)} readings):
{json.dumps(lookback_data, indent=2)}

Task: Detect anomalies in the sensor readings and provide:
1. Anomaly score (0-1, where 1 is highly anomalous)
2. Identified anomalous time steps
3. Most anomalous sensors
4. Brief explanation of detected patterns
5. Forecast for next {config.forecast_horizon} time steps

Return the analysis as a JSON object.
"""

                # Call NV Tesseract NIM
                response = await llm.acomplete(prompt)

                # Extract the response text
                response_text = response.text if hasattr(response, 'text') else str(response)

                # Try to parse as JSON, or return as-is
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    result = {
                        "analysis": response_text,
                        "unit_number": unit_number,
                        "dataset": dataset_name,
                        "data_points_analyzed": len(lookback_data)
                    }

                # Add metadata
                result["model"] = config.model_name
                result["lookback_period"] = config.lookback_period
                result["forecast_horizon"] = config.forecast_horizon

                return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error processing sensor data: {str(e)}",
                "raw_result": sql_result
            })

    yield FunctionInfo.from_fn(
        _detect_anomalies,
        input_schema=AnomalyDetectionInput,
        description=(
            "Detect anomalies in turbofan engine sensor data using NV Tesseract foundation model. "
            "Analyzes time-series sensor readings to identify unusual patterns and forecast future values. "
            "Provides anomaly scores, identifies problematic sensors, and explains detected patterns."
        )
    )
