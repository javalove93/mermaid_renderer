#!/bin/bash

# setup_venv.sh - Create Python environment with uv (idempotent)
# This script creates a virtual environment using uv and installs required packages

set -e  # Exit on any error

# Default environment directory
VENV_DIR=".venv"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install uv first."
    echo "Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Check if virtual environment already exists
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR"
    echo "Activating existing environment..."
    source "$VENV_DIR/bin/activate"
else
    echo "Creating new virtual environment at $VENV_DIR..."
    uv venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found in current directory"
    exit 1
fi

# Install/update packages
echo "Installing/updating packages from requirements.txt..."
uv pip install -r requirements.txt

echo "✅ Virtual environment setup complete!"
echo "To activate the environment, run: source $VENV_DIR/bin/activate"
echo "To run the application, use: ./run.sh"
