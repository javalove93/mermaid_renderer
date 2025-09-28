#!/bin/bash

# run.sh - Run Python backend with uv environment activation
# This script activates the virtual environment and runs the Flask application

set -e  # Exit on any error

# Default environment directory
VENV_DIR=".venv"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Please run ./setup_venv.sh first."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found in current directory"
    exit 1
fi

# Set default port if not set
export PORT=${PORT:-5001}

# Run the Flask application in debug mode
export FLASK_DEBUG=1
export FLASK_ENV=development
python app.py
