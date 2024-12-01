"""
Adapt s3 to package_streaming
"""

from __future__ import annotations

import typing
from contextlib import closing
from typing import Any

from . import package_streaming

if typing.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import Client
    from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef
else:
    Client = GetObjectOutputTypeDef = None

from .url import conda_reader_for_url

__all__ = ["stream_conda_info", "conda_reader_for_s3"]


class ResponseFacade:
    def __init__(self, response: GetObjectOutputTypeDef):
        self.response = response
        self.raw: Any = response["Body"]

    def raise_for_status(self):
        # s3 get_object raises automatically?
        pass

    @property
    def status_code(self):
        return self.response["ResponseMetadata"]["HTTPStatusCode"]

    @property
    def headers(self):
        # a case-sensitive dict; keys may be lowercased always?
        return self.response["ResponseMetadata"]["HTTPHeaders"]

    def iter_content(self, n: int):
        return iter(lambda: self.raw.read(n), b"")


class SessionFacade:
    """
    Make s3 client look just enough like a requests.session for LazyZipOverHTTP
    """

    def __init__(self, client: Client, bucket: str, key: str):
        self.client = client
        self.bucket = bucket
        self.key = key

    def get(self, url, *, headers: dict | None = None, stream=True):
        if headers and "Range" in headers:
            response = self.client.get_object(
                Bucket=self.bucket, Key=self.key, Range=headers["Range"]
            )
        else:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key)
        return ResponseFacade(response)


def stream_conda_info(client, bucket, key):
    """
    Yield (tar, member) for conda package.

    Just "info/" for .conda, all members for tar.
    """
    filename, conda = conda_reader_for_s3(client, bucket, key)

    with closing(conda):
        yield from package_streaming.stream_conda_info(filename, conda)


def conda_reader_for_s3(client: Client, bucket: str, key: str):
    """
    Return (name, file_like) suitable for package_streaming APIs
    """
    session: Any = SessionFacade(client, bucket, key)
    return conda_reader_for_url(key, session)
