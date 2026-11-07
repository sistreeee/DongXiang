#!/bin/sh
set -eu

case "$0" in
  */*) SETUP_SCRIPT_DIR=${0%/*} ;;
  *) SETUP_SCRIPT_DIR=. ;;
esac
cd "$SETUP_SCRIPT_DIR/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ is required"; print("Python", sys.version.split()[0])'
"$PYTHON_BIN" -m unittest discover -s tests -v

echo "Setup complete. Run: $PYTHON_BIN cloud-location-check.py"
