# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from requests import ConnectionError, HTTPError, Session  # noqa: F401
from requests.adapters import DEFAULT_POOLBLOCK, BaseAdapter, HTTPAdapter  # noqa: F401
from requests.auth import AuthBase, _basic_auth_str  # noqa: F401
from requests.cookies import extract_cookies_to_jar  # noqa: F401
from requests.exceptions import (  # noqa: F401
    ChunkedEncodingError,
    InvalidSchema,
    SSLError,
)
from requests.exceptions import ProxyError as RequestsProxyError  # noqa: F401
from requests.hooks import dispatch_hook  # noqa: F401
from requests.models import PreparedRequest, Response  # noqa: F401
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # noqa: F401
from requests.packages.urllib3.util.retry import Retry  # noqa: F401
from requests.structures import CaseInsensitiveDict  # noqa: F401
from requests.utils import get_auth_from_url, get_netrc_auth  # noqa: F401
