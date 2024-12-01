import atexit
import base64
import errno
import os
import sys
from os.path import dirname, exists
from threading import RLock

DPREFIX = os.environ.get("ANACONDA_ANON_USAGE_DEBUG_PREFIX") or ""
DEBUG = bool(os.environ.get("ANACONDA_ANON_USAGE_DEBUG")) or DPREFIX

# When creating a new environment, the environment token will be
# created in advance of the action creation of the standard conda
# directory structure. If we write the token to its location and
# then the creation is interrupted, the directory will now be in
# a state where conda is unwilling to install into it, thinking
# it is a non-empty non-conda directory.
DEFERRED = []

# While lru_cache is thread safe, it does not prevent two threads
# from beginning the same computation. This simple cache mechanism
# uses a lock to ensure that only one thread even attempts.
CACHE = {}
LOCK = RLock()

# Causes tokens reads to fail (for testing). The string should contain
# the token types that should fail; e.g., c, s, e
READ_CHAOS = os.environ.get("ANACONDA_ANON_USAGE_READ_CHAOS") or ""
# Causes token writes to fail (for testing). The string should contain
# the token types that should fail; c, e
WRITE_CHAOS = os.environ.get("ANACONDA_ANON_USAGE_WRITE_CHAOS") or ""

WRITE_SUCCESS = 0
WRITE_DEFER = 1
WRITE_FAIL = 2


def cached(func):
    def call_if_needed(*args, **kwargs):
        global CACHE
        key = (func.__name__, args, tuple(kwargs.items()))
        if key not in CACHE:
            with LOCK:
                # Need to check again, just in case the
                # computation was happening between the
                # first check and the lock acquisition.
                if key not in CACHE:
                    CACHE[key] = func(*args, **kwargs)
        return CACHE[key]

    return call_if_needed


def _cache_clear():
    global CACHE
    CACHE.clear()


def _debug(s, *args, error=False):
    if error and not DEBUG:
        # Suppress error output in --json mode. This accommodates
        # processes that might be using --json mode and merging
        # stdout and stderr together. If DEBUG is True we assume
        # this accommodation is not necessary. The import is
        # deferred here as well to reduce the likelihood of a
        # circular import issue.
        from conda.base.context import context

        error = not context.json
    if error or DEBUG:
        print((DPREFIX + s) % args, file=sys.stderr)


def _random_token(what="random"):
    data = os.urandom(16)
    result = base64.urlsafe_b64encode(data).strip(b"=").decode("ascii")
    _debug("Generated %s token: %s", what, result)
    return result


def _final_attempt():
    """
    Called upon the graceful exit from conda, this attempts to
    write an environment token that was deferred because the
    environment directory was not yet available.
    """
    global DEFERRED
    for must_exist, fpath, token in DEFERRED:
        _write_attempt(must_exist, fpath, token)


atexit.register(_final_attempt)


def _write_attempt(must_exist, fpath, client_token, emulate_fail=False):
    """
    Attempt to write the token to the given location.
    Return True with success, False otherwise.
    """
    if must_exist and not exists(must_exist):
        _debug("Directory not ready: %s", must_exist)
        return WRITE_DEFER
    try:
        if emulate_fail:
            raise OSError(errno.EROFS, "Testing permissions issues")
        os.makedirs(dirname(fpath), exist_ok=True)
        with open(fpath, "w") as fp:
            fp.write(client_token)
        _debug("Token saved: %s", fpath)
        return WRITE_SUCCESS
    except Exception as exc:
        # If we get here, a second attempt is unlikely to succeed,
        # so we return a code to indicate that we should not re-attempt.
        if getattr(exc, "errno", None) in (errno.EACCES, errno.EPERM, errno.EROFS):
            _debug("No write permissions; cannot write token")
        else:
            _debug(
                "Unexpected error writing token file:\n  path: %s\n  exception: %s",
                fpath,
                exc,
                error=True,
            )
        return WRITE_FAIL


def _saved_token(fpath, what, must_exist=None):
    """
    Implements the saved token functionality. If the specified
    file exists, and contains a token with the right format,
    return it. Otherwise, generate a new one and save it in
    this location. If that fails, return an empty string.
    """
    global DEFERRED
    client_token = ""
    _debug("%s token path: %s", what.capitalize(), fpath)
    if what[0] in READ_CHAOS:
        _debug("Pretending %s token is not present", what)
    elif exists(fpath):
        try:
            # Use just the first line of the file, if it exists
            with open(fpath) as fp:
                client_token = "".join(fp.read().splitlines()[:1])
            _debug("Retrieved %s token: %s", what, client_token)
        except Exception as exc:
            _debug("Unexpected error reading: %s\n  %s", fpath, exc, error=True)
    if len(client_token) < 22:
        if len(client_token) > 0:
            _debug("Generating longer token")
        client_token = _random_token(what)
        status = _write_attempt(must_exist, fpath, client_token, what[0] in WRITE_CHAOS)
        if status == WRITE_FAIL:
            _debug("Returning blank %s token", what)
            return ""
        elif status == WRITE_DEFER:
            # If the environment has not yet been created we need
            # to defer the token write until later.
            _debug("Deferring token write")
            DEFERRED.append((must_exist, fpath, client_token))
    return client_token
