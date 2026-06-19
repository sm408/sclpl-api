#!/bin/bash
# SCLPLAPI Portable Launcher for Linux/macOS
# Run: ./sclplapi.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.11+ from https://python.org"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".installed" ]; then
    echo ""
    echo "Installing SCLPLAPI dependencies..."
    echo ""
    pip3 install -e ".[all]" --quiet 2>/dev/null || pip install -e ".[all]" --quiet
    touch .installed
    echo "Installation complete!"
    echo ""
fi

# Create data directory if needed
mkdir -p data

# Launch
python3 -m app "$@" 2>/dev/null || python -m app "$@"
