#!/usr/bin/env sh

# Install dependencies
pip install -r requirements.txt

# Run tests and generate coverage reports
coverage run -m unittest discover -s . -p "app_unittest.py"
coverage xml

# Cleanup
rm -rf __pycache__
