# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Requests session configured with all accepted scheme adapters."""

from __future__ import annotations

from fnmatch import fnmatch
from functools import lru_cache
from logging import getLogger
from threading import local

from ... import CondaError
from ...auxlib.ish import dals
from ...base.constants import CONDA_HOMEPAGE_URL
from ...base.context import context
from ...common.url import (
    add_username_and_password,
    get_proxy_username_and_pass,
    split_anaconda_token,
    urlparse,
)
from ...exceptions import ProxyError
from ...models.channel import Channel
from ..anaconda_client import read_binstar_tokens
from . import (
    AuthBase,
    BaseAdapter,
    Retry,
    Session,
    _basic_auth_str,
    extract_cookies_to_jar,
    get_auth_from_url,
    get_netrc_auth,
)
from .adapters.ftp import FTPAdapter
from .adapters.http import HTTPAdapter
from .adapters.localfs import LocalFSAdapter
from .adapters.s3 import S3Adapter

log = getLogger(__name__)
RETRIES = 3


CONDA_SESSION_SCHEMES = frozenset(
    (
        "http",
        "https",
        "ftp",
        "s3",
        "file",
    )
)


class EnforceUnusedAdapter(BaseAdapter):
    def send(self, request, *args, **kwargs):
        message = dals(
            f"""
        EnforceUnusedAdapter called with url {request.url}
        This command is using a remote connection in offline mode.
        """
        )
        raise RuntimeError(message)

    def close(self):
        raise NotImplementedError()


def get_channel_name_from_url(url: str) -> str | None:
    """
    Given a URL, determine the channel it belongs to and return its name.
    """
    return Channel.from_url(url).canonical_name


@lru_cache(maxsize=None)
def get_session(url: str):
    """
    Function that determines the correct Session object to be returned
    based on the URL that is passed in.
    """
    channel_name = get_channel_name_from_url(url)

    # If for whatever reason a channel name can't be determined, (should be unlikely)
    # we just return the default session object.
    if channel_name is None:
        return CondaSession()

    # We ensure here if there are duplicates defined, we choose the last one
    channel_settings = {}
    for settings in context.channel_settings:
        channel = settings.get("channel", "")
        if channel == channel_name:
            # First we check for exact match
            channel_settings = settings
            continue

        # If we don't have an exact match, we attempt to match a URL pattern
        parsed_url = urlparse(url)
        parsed_setting = urlparse(channel)

        # We require that the schemes must be identical to prevent downgrade attacks.
        # This includes the case of a scheme-less pattern like "*", which is not allowed.
        if parsed_setting.scheme != parsed_url.scheme:
            continue

        url_without_schema = parsed_url.netloc + parsed_url.path
        pattern = parsed_setting.netloc + parsed_setting.path
        if fnmatch(url_without_schema, pattern):
            channel_settings = settings

    auth_handler = channel_settings.get("auth", "").strip() or None

    # Return default session object
    if auth_handler is None:
        return CondaSession()

    auth_handler_cls = context.plugin_manager.get_auth_handler(auth_handler)

    if not auth_handler_cls:
        return CondaSession()

    return CondaSession(auth=auth_handler_cls(channel_name))


def get_session_storage_key(auth) -> str:
    """
    Function that determines which storage key to use for our CondaSession object caching
    """
    if auth is None:
        return "default"

    if isinstance(auth, tuple):
        return hash(auth)

    auth_type = type(auth)

    return f"{auth_type.__module__}.{auth_type.__qualname__}::{auth.channel_name}"


class CondaSessionType(type):
    """
    Takes advice from https://github.com/requests/requests/issues/1871#issuecomment-33327847
    and creates one Session instance per thread.
    """

    def __new__(mcs, name, bases, dct):
        dct["_thread_local"] = local()
        return super().__new__(mcs, name, bases, dct)

    def __call__(cls, **kwargs):
        storage_key = get_session_storage_key(kwargs.get("auth"))

        try:
            return cls._thread_local.sessions[storage_key]
        except AttributeError:
            session = super().__call__(**kwargs)
            cls._thread_local.sessions = {storage_key: session}
        except KeyError:
            session = cls._thread_local.sessions[storage_key] = super().__call__(
                **kwargs
            )

        return session


class CondaSession(Session, metaclass=CondaSessionType):
    def __init__(self, auth: AuthBase | tuple[str, str] | None = None):
        """
        :param auth: Optionally provide ``requests.AuthBase`` compliant objects
        """
        super().__init__()

        self.auth = auth or CondaHttpAuth()

        self.proxies.update(context.proxy_servers)

        ssl_context = None
        if context.ssl_verify == "truststore":
            try:
                import ssl

                import truststore

                ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            except ImportError:
                raise CondaError(
                    "The `ssl_verify: truststore` setting is only supported on"
                    "Python 3.10 or later."
                )
            self.verify = True
        else:
            self.verify = context.ssl_verify

        if context.offline:
            unused_adapter = EnforceUnusedAdapter()
            self.mount("http://", unused_adapter)
            self.mount("https://", unused_adapter)
            self.mount("ftp://", unused_adapter)
            self.mount("s3://", unused_adapter)

        else:
            # Configure retries
            retry = Retry(
                total=context.remote_max_retries,
                backoff_factor=context.remote_backoff_factor,
                status_forcelist=[413, 429, 500, 503],
                raise_on_status=False,
                respect_retry_after_header=False,
            )
            http_adapter = HTTPAdapter(max_retries=retry, ssl_context=ssl_context)
            self.mount("http://", http_adapter)
            self.mount("https://", http_adapter)
            self.mount("ftp://", FTPAdapter())
            self.mount("s3://", S3Adapter())

        self.mount("file://", LocalFSAdapter())

        self.headers["User-Agent"] = context.user_agent

        if context.client_ssl_cert_key:
            self.cert = (context.client_ssl_cert, context.client_ssl_cert_key)
        elif context.client_ssl_cert:
            self.cert = context.client_ssl_cert

    @classmethod
    def cache_clear(cls):
        try:
            cls._thread_local.sessions.clear()
        except AttributeError:
            # AttributeError: thread's session cache has not been initialized
            pass


class CondaHttpAuth(AuthBase):
    # TODO: make this class thread-safe by adding some of the requests.auth.HTTPDigestAuth() code

    def __call__(self, request):
        request.url = CondaHttpAuth.add_binstar_token(request.url)
        self._apply_basic_auth(request)
        request.register_hook("response", self.handle_407)
        return request

    @staticmethod
    def _apply_basic_auth(request):
        # this logic duplicated from Session.prepare_request and PreparedRequest.prepare_auth
        url_auth = get_auth_from_url(request.url)
        auth = url_auth if any(url_auth) else None

        if auth is None:
            # look for auth information in a .netrc file
            auth = get_netrc_auth(request.url)

        if isinstance(auth, tuple) and len(auth) == 2:
            request.headers["Authorization"] = _basic_auth_str(*auth)

        return request

    @staticmethod
    def add_binstar_token(url):
        clean_url, token = split_anaconda_token(url)
        if not token and context.add_anaconda_token:
            for binstar_url, token in read_binstar_tokens().items():
                if clean_url.startswith(binstar_url):
                    log.debug("Adding anaconda token for url <%s>", clean_url)
                    from ...models.channel import Channel

                    channel = Channel(clean_url)
                    channel.token = token
                    return channel.url(with_credentials=True)
        return url

    @staticmethod
    def handle_407(response, **kwargs):  # pragma: no cover
        """
        Prompts the user for the proxy username and password and modifies the
        proxy in the session object to include it.

        This method is modeled after
          * requests.auth.HTTPDigestAuth.handle_401()
          * requests.auth.HTTPProxyAuth
          * the previous conda.fetch.handle_proxy_407()

        It both adds 'username:password' to the proxy URL, as well as adding a
        'Proxy-Authorization' header.  If any of this is incorrect, please file an issue.

        """
        # kwargs = {'verify': True, 'cert': None, 'proxies': {}, 'stream': False,
        #           'timeout': (3.05, 60)}

        if response.status_code != 407:
            return response

        # Consume content and release the original connection
        # to allow our new request to reuse the same one.
        response.content
        response.close()

        proxies = kwargs.pop("proxies")

        proxy_scheme = urlparse(response.url).scheme
        if proxy_scheme not in proxies:
            raise ProxyError(
                dals(
                    f"""
            Could not find a proxy for {proxy_scheme!r}. See
            {CONDA_HOMEPAGE_URL}/docs/html#configure-conda-for-use-behind-a-proxy-server
            for more information on how to configure proxies.
            """
                )
            )

        # fix-up proxy_url with username & password
        proxy_url = proxies[proxy_scheme]
        username, password = get_proxy_username_and_pass(proxy_scheme)
        proxy_url = add_username_and_password(proxy_url, username, password)
        proxy_authorization_header = _basic_auth_str(username, password)
        proxies[proxy_scheme] = proxy_url
        kwargs["proxies"] = proxies

        prep = response.request.copy()
        extract_cookies_to_jar(prep._cookies, response.request, response.raw)
        prep.prepare_cookies(prep._cookies)
        prep.headers["Proxy-Authorization"] = proxy_authorization_header

        _response = response.connection.send(prep, **kwargs)
        _response.history.append(response)
        _response.request = prep

        return _response
