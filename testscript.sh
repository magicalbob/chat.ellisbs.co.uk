#!/usr/bin/env sh

set -e  # Exit on any error

# Install dependencies
pip install -e ".[dev]"
pip install pytest
export OPENAI_API_KEY=dummy
export CLAUDE_API_KEY=dummy

# Run tests with coverage
coverage run -m pytest --exitfirst --disable-warnings

# Check if any tests were executed
TEST_COUNT=$(coverage report | grep "TOTAL" | awk '{print $2}')
if [ "$TEST_COUNT" -eq "0" ]; then
  echo "❌ No tests were run. Failing the job."
  exit 1
fi

# Generate XML report
coverage xml

# Cleanup
rm -rf __pycache__
