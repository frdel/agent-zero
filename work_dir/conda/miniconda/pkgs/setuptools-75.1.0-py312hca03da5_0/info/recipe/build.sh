#!/bin/bash

export SETUPTOOLS_DISABLE_VERSIONED_EASY_INSTALL_SCRIPT=1
export DISTRIBUTE_DISABLE_VERSIONED_EASY_INSTALL_SCRIPT=1

$PYTHON setup.py install --single-version-externally-managed --record=record.txt
