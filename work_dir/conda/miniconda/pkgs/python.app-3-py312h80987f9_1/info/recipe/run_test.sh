#!/usr/bin/env bash

echo "Running tests to compare python, python.app, pythonw versions..."

PYTHON_VERSION=`python -V`
PYTHONW_VERSION=`pythonw -V`
PYTHONAPP_VERSION=`python.app -V`

if [ "$PYTHON_VERSION" != "$PYTHONW_VERSION" ]; then
  echo "Version mismatch: python <> pythonw"
  exit 1
elif [ "$PYTHON_VERSION" != "$PYTHONAPP_VERSION" ]; then
  echo "Version mismatch: python <> python.app"
  exit 1
elif [ "$PYTHONW_VERSION" != "$PYTHONAPP_VERSION" ]; then
  echo "Version mismatch: pythonw <> python.app"
  exit 1
fi

echo "...OK."
