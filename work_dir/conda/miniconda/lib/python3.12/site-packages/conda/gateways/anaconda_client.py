# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Anaconda-client (binstar) token management for CondaSession."""

import os
import re
from logging import getLogger
from os.path import isdir, isfile, join
from stat import S_IREAD, S_IWRITE

from platformdirs import user_config_dir

from ..common.url import quote_plus, unquote_plus
from .disk.delete import rm_rf

log = getLogger(__name__)


def replace_first_api_with_conda(url):
    # replace first occurrence of 'api' with 'conda' in url
    return re.sub(r"([./])api([./]|$)", r"\1conda\2", url, count=1)


def _get_binstar_token_directory():
    if "BINSTAR_CONFIG_DIR" in os.environ:
        return os.path.join(os.environ["BINSTAR_CONFIG_DIR"], "data")
    else:
        return user_config_dir(appname="binstar", appauthor="ContinuumIO")


def read_binstar_tokens():
    tokens = {}
    token_dir = _get_binstar_token_directory()
    if not isdir(token_dir):
        return tokens

    for tkn_entry in os.scandir(token_dir):
        if tkn_entry.name[-6:] != ".token":
            continue
        url = re.sub(r"\.token$", "", unquote_plus(tkn_entry.name))
        with open(tkn_entry.path) as f:
            token = f.read()
        tokens[url] = tokens[replace_first_api_with_conda(url)] = token
    return tokens


def set_binstar_token(url, token):
    token_dir = _get_binstar_token_directory()
    if not isdir(token_dir):
        os.makedirs(token_dir)

    tokenfile = join(token_dir, f"{quote_plus(url)}.token")

    if isfile(tokenfile):
        os.unlink(tokenfile)
    with open(tokenfile, "w") as fd:
        fd.write(token)
    os.chmod(tokenfile, S_IWRITE | S_IREAD)


def remove_binstar_token(url):
    token_dir = _get_binstar_token_directory()
    tokenfile = join(token_dir, f"{quote_plus(url)}.token")
    rm_rf(tokenfile)


if __name__ == "__main__":
    print(read_binstar_tokens())
