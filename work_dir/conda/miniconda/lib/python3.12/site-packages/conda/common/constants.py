# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common constants."""

from ..auxlib import NULL

# Use this NULL object when needing to distinguish a value from None
# For example, when parsing json, you may need to determine if a json key was given and set
#   to null, or the key didn't exist at all.  There could be a bit of potential confusion here,
#   because in python null == None, while here I'm defining NULL to mean 'not defined'.
NULL = NULL

# Custom "trace" logging level for output more verbose than debug logs (logging.DEBUG == 10).
TRACE = 5
