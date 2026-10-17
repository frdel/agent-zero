import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from flaredantic import NotifyEvent


TUNNEL_READY_TIMEOUT_ENV = "A0_TUNNEL_READY_TIMEOUT"
TUNNEL_READY_TIMEOUT_DEFAULT = 45.0
TUNNEL_READY_TIMEOUT_MAX = 300.0
TUNNEL_READY_INTERVAL = 0.5
TUNNEL_READY_REQUEST_TIMEOUT = 5.0


def event_value(event):
    return event.value if hasattr(event, "value") else event


def tunnel_ready_timeout():
    """Readiness wait budget in seconds; <= 0 disables the verification."""
    raw = (os.environ.get(TUNNEL_READY_TIMEOUT_ENV) or "").strip()
    if not raw:
        return TUNNEL_READY_TIMEOUT_DEFAULT
    try:
        value = float(raw)
    except ValueError:
        return TUNNEL_READY_TIMEOUT_DEFAULT
    return max(0.0, min(value, TUNNEL_READY_TIMEOUT_MAX))


def probe_tunnel_url(url):
    """Return True once the tunnel hostname resolves and the edge answers.

    Quick tunnels are announced on stdout before the hostname is served, so an
    immediate request is answered with NXDOMAIN. Any HTTP response (including
    3xx/4xx) proves the tunnel edge is serving the hostname.
    """
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        socket.getaddrinfo(host, port)
    except OSError:
        return False

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AgentZero-TunnelReadiness"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=TUNNEL_READY_REQUEST_TIMEOUT):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def wait_for_tunnel_ready(
    url,
    timeout=None,
    interval=TUNNEL_READY_INTERVAL,
    probe=None,
    sleep=time.sleep,
    clock=time.monotonic,
):
    """Block until the tunnel URL answers; True once it is reachable.

    Returns True immediately when the wait budget is disabled (<= 0).
    """
    if not url:
        return False
    if timeout is None:
        timeout = tunnel_ready_timeout()
    if timeout <= 0:
        return True
    probe = probe or probe_tunnel_url
    deadline = clock() + timeout
    while True:
        try:
            if probe(url):
                return True
        except Exception:
            pass
        if clock() >= deadline:
            return False
        sleep(interval)


class TunnelHelper:
    def __init__(self, port, notify=None):
        self.port = port
        self.notify_callback = notify
        self.tunnel = None
        self.tunnel_url = None

    def _notify(self, event, message, data=None):
        if callable(self.notify_callback):
            self.notify_callback(event, message, data)

    def notify_starting(self, label):
        self._notify(
            NotifyEvent.CREATING_TUNNEL,
            f"Starting {label} on port {self.port}...",
        )

    def notify_url_ready(self, label, url):
        self._notify(
            NotifyEvent.TUNNEL_URL,
            f"{label} URL is ready",
            {"url": url},
        )

    def notify_url_pending(self, label, url):
        self._notify(
            NotifyEvent.INFO,
            f"{label} URL was published but is not reachable yet; it may take a moment.",
            {"url": url},
        )

    def notify_stopped(self, label):
        self._notify(NotifyEvent.TUNNEL_STOPPED, f"{label} stopped")


class FlaredanticTunnelHelper(TunnelHelper):
    label = "Remote Control"

    # Overridable seams for tests: callable(url) -> bool readiness probe and
    # readiness wait budget in seconds.
    ready_probe = None
    ready_timeout = None

    def build_tunnel(self):
        raise NotImplementedError

    def start(self):
        self.notify_starting(self.label)
        self.tunnel = self.build_tunnel()
        self.tunnel.start()
        self.tunnel_url = getattr(self.tunnel, "tunnel_url", None)
        if self.tunnel_url:
            ready = wait_for_tunnel_ready(
                self.tunnel_url,
                timeout=self.ready_timeout,
                probe=self.ready_probe,
            )
            if not ready:
                self.notify_url_pending(self.label, self.tunnel_url)
            self.notify_url_ready(self.label, self.tunnel_url)
        return self.tunnel_url

    def stop(self):
        if self.tunnel:
            self.tunnel.stop()
        self.tunnel_url = None
        self.notify_stopped(self.label)
        return True
