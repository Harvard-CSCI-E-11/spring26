#!/bin/bash
set -e

# Create site-packages directory
mkdir -p python/lib/python3.12/site-packages

# Install requirements into the site-packages directory
pip install -r requirements.txt -t python/lib/python3.12/site-packages --no-deps

# Copy the source files
cp *.py python/
cp -r templates python/
cp -r static python/ 2>/dev/null || true

echo "Build completed. Lambda package is in the 'python' directory."
