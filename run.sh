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
export PORT=${PORT:-5000}

# External port for socat forwarding
EXTERNAL_PORT=8083

echo "Starting Flask application on port $PORT..."
echo "Setting up port forwarding from external port $EXTERNAL_PORT to internal port $PORT..."

# Check if socat is available
if ! command -v socat &> /dev/null; then
    echo "Error: socat is not installed. Please install socat first."
    echo "On Ubuntu/Debian: sudo apt-get install socat"
    echo "On macOS: brew install socat"
    exit 1
fi

# Start socat in background for port forwarding
echo "Starting port forwarding with socat..."
socat TCP-LISTEN:$EXTERNAL_PORT,fork,reuseaddr TCP:localhost:$PORT &
SOCAT_PID=$!

# Function to cleanup on exit
cleanup() {
    echo "Stopping port forwarding and Flask application..."
    kill $SOCAT_PID 2>/dev/null || true
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

echo "Port forwarding active:"
echo "  External access: http://localhost:$EXTERNAL_PORT"
echo "  Internal Flask: http://localhost:$PORT"
echo "  English word quiz: http://localhost:$EXTERNAL_PORT/english"
echo "Press Ctrl+C to stop both port forwarding and Flask application"

# Run the Flask application in debug mode
export FLASK_DEBUG=1
export FLASK_ENV=development
python app.py
