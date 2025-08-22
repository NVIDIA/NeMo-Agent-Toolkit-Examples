#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2024-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Setup script for EXAMPLE_NAME
# Replace EXAMPLE_NAME with your actual example name

echo "Setting up EXAMPLE_NAME..."

# Example: Check if required environment variables are set
if [ -z "$NVIDIA_API_KEY" ]; then
    echo "Warning: NVIDIA_API_KEY environment variable is not set"
    echo "Please set it before running the workflow:"
    echo "export NVIDIA_API_KEY=<YOUR_API_KEY>"
fi

# Example: Create necessary directories
# mkdir -p output_dir

# Example: Download required data files
# echo "Downloading sample data..."
# curl -o data/external_data.json https://example.com/data.json

# Example: Install additional Python dependencies
# echo "Installing additional dependencies..."
# pip install some-extra-package

# Example: Set up configuration files
# echo "Setting up configuration..."
# cp configs/config.yml.template configs/config.yml

echo "Setup complete!"
echo "You can now run the workflow with:"
echo "nat run --config_file configs/config.yml --input 'Your input here'"
