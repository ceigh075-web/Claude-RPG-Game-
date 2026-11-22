#!/usr/bin/env sh
# Runs Kindred Roads from source (Linux/macOS). Needs Python 3.11+.
cd "$(dirname "$0")"
python3 -c "import pygame" 2>/dev/null || python3 -m pip install --user -r requirements.txt
exec python3 main.py "$@"
