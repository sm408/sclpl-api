#!/bin/bash
# SCLPLAPI Launcher for Linux/macOS
# Run: ./sclplapi.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".installed" ]; then
    echo ""
    echo "Installing SCLPLAPI..."
    echo ""
    pip install -e . --quiet
    touch .installed
    echo "Done!"
    echo ""
fi

# Create data directory
mkdir -p data

# Launch TUI
python3 -m app "$@"
