#!/usr/bin/env sh
set -e  # Exit immediately on error

# Install dependencies
pip install -r requirements.txt

# Run tests and generate coverage reports
python3 -m unittest discover -s . -p "app_unittest.py"
coverage run -m unittest discover -s . -p "app_unittest.py"
coverage xml

# Cleanup
rm -rf __pycache__
