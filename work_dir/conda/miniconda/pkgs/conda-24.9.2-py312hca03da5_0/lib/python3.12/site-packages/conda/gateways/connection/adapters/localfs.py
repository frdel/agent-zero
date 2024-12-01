# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Defines local filesystem transport adapter for CondaSession (requests.Session)."""

import json
from email.utils import formatdate
from logging import getLogger
from mimetypes import guess_type
from os import stat
from tempfile import SpooledTemporaryFile

from ....common.compat import ensure_binary
from ....common.path import url_to_path
from .. import BaseAdapter, CaseInsensitiveDict, Response

log = getLogger(__name__)


class LocalFSAdapter(BaseAdapter):
    def send(
        self, request, stream=None, timeout=None, verify=None, cert=None, proxies=None
    ):
        pathname = url_to_path(request.url)

        resp = Response()
        resp.status_code = 200
        resp.url = request.url

        try:
            stats = stat(pathname)
        except OSError as exc:
            resp.status_code = 404
            message = {
                "error": "file does not exist",
                "path": pathname,
                "exception": repr(exc),
            }
            fh = SpooledTemporaryFile()
            fh.write(ensure_binary(json.dumps(message)))
            fh.seek(0)
            resp.raw = fh
            resp.close = resp.raw.close
        else:
            modified = formatdate(stats.st_mtime, usegmt=True)
            content_type = guess_type(pathname)[0] or "text/plain"
            resp.headers = CaseInsensitiveDict(
                {
                    "Content-Type": content_type,
                    "Content-Length": stats.st_size,
                    "Last-Modified": modified,
                }
            )

            resp.raw = open(pathname, "rb")
            resp.close = resp.raw.close
        return resp

    def close(self):
        pass  # pragma: no cover
