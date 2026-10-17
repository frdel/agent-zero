import enum
import importlib
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeNotifyEvent(enum.Enum):
    CREATING_TUNNEL = "creating_tunnel"
    TUNNEL_URL = "tunnel_url"
    TUNNEL_STOPPED = "tunnel_stopped"
    INFO = "info"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def tunnel_common_module(monkeypatch):
    fake_flaredantic = types.SimpleNamespace(NotifyEvent=FakeNotifyEvent)
    monkeypatch.setitem(sys.modules, "flaredantic", fake_flaredantic)
    sys.modules.pop("helpers.tunnel_common", None)
    module = importlib.import_module("helpers.tunnel_common")
    yield module
    sys.modules.pop("helpers.tunnel_common", None)


def test_wait_for_tunnel_ready_gives_up_when_probe_never_succeeds(
    tunnel_common_module,
):
    clock = FakeClock()
    calls = []

    def probe(url):
        calls.append(url)
        return False

    ready = tunnel_common_module.wait_for_tunnel_ready(
        "https://never.example",
        timeout=2,
        interval=1,
        probe=probe,
        sleep=clock.sleep,
        clock=clock,
    )

    assert ready is False
    assert calls == ["https://never.example"] * 3


def test_wait_for_tunnel_ready_returns_once_probe_succeeds(tunnel_common_module):
    clock = FakeClock()
    results = iter([False, False, True])

    ready = tunnel_common_module.wait_for_tunnel_ready(
        "https://late.example",
        timeout=10,
        interval=1,
        probe=lambda url: next(results),
        sleep=clock.sleep,
        clock=clock,
    )

    assert ready is True


def test_wait_for_tunnel_ready_returns_false_without_url(tunnel_common_module):
    probed = []

    ready = tunnel_common_module.wait_for_tunnel_ready(
        "", probe=lambda url: probed.append(url) or True
    )

    assert ready is False
    assert probed == []


def test_wait_for_tunnel_ready_disabled_budget_skips_probe(
    tunnel_common_module, monkeypatch
):
    monkeypatch.setenv(tunnel_common_module.TUNNEL_READY_TIMEOUT_ENV, "0")
    probed = []

    ready = tunnel_common_module.wait_for_tunnel_ready(
        "https://disabled.example",
        probe=lambda url: probed.append(url) or False,
    )

    assert ready is True
    assert probed == []


def test_tunnel_ready_timeout_reads_env_and_clamps(tunnel_common_module, monkeypatch):
    monkeypatch.delenv(tunnel_common_module.TUNNEL_READY_TIMEOUT_ENV, raising=False)
    assert (
        tunnel_common_module.tunnel_ready_timeout()
        == tunnel_common_module.TUNNEL_READY_TIMEOUT_DEFAULT
    )

    monkeypatch.setenv(tunnel_common_module.TUNNEL_READY_TIMEOUT_ENV, "not-a-number")
    assert (
        tunnel_common_module.tunnel_ready_timeout()
        == tunnel_common_module.TUNNEL_READY_TIMEOUT_DEFAULT
    )

    monkeypatch.setenv(tunnel_common_module.TUNNEL_READY_TIMEOUT_ENV, "7.5")
    assert tunnel_common_module.tunnel_ready_timeout() == 7.5

    monkeypatch.setenv(tunnel_common_module.TUNNEL_READY_TIMEOUT_ENV, "9999")
    assert (
        tunnel_common_module.tunnel_ready_timeout()
        == tunnel_common_module.TUNNEL_READY_TIMEOUT_MAX
    )


def test_probe_tunnel_url_rejects_unusable_hostnames(tunnel_common_module):
    assert tunnel_common_module.probe_tunnel_url("") is False
    assert tunnel_common_module.probe_tunnel_url("not-a-url") is False


def make_helper(tunnel_common_module, notifications, url):
    class FakeTunnel:
        def __init__(self):
            self.tunnel_url = url

        def start(self):
            return self.tunnel_url

        def stop(self):
            return None

    class Helper(tunnel_common_module.FlaredanticTunnelHelper):
        label = "Cloudflare Tunnel"

        def build_tunnel(self):
            return FakeTunnel()

    helper = Helper(
        8080,
        notify=lambda event, message, data=None: notifications.append(
            {
                "event": tunnel_common_module.event_value(event),
                "message": message,
                "data": data,
            }
        ),
    )
    return helper


def test_helper_waits_for_readiness_before_reporting_url(tunnel_common_module):
    notifications = []
    url = "https://fresh-tunnel.trycloudflare.com"
    helper = make_helper(tunnel_common_module, notifications, url)
    probes = []

    def probe(candidate):
        probes.append(candidate)
        return len(probes) > 1

    helper.ready_probe = probe
    helper.ready_timeout = 5

    assert helper.start() == url
    assert probes == [url, url]
    assert notifications[0]["event"] == "creating_tunnel"
    assert notifications[-1]["event"] == "tunnel_url"
    assert notifications[-1]["data"] == {"url": url}


def test_helper_flags_pending_url_when_probe_times_out(tunnel_common_module):
    notifications = []
    url = "https://slow-tunnel.trycloudflare.com"
    helper = make_helper(tunnel_common_module, notifications, url)
    helper.ready_probe = lambda candidate: False
    helper.ready_timeout = 0.01

    assert helper.start() == url
    assert [notification["event"] for notification in notifications] == [
        "creating_tunnel",
        "info",
        "tunnel_url",
    ]


def test_helper_reports_url_without_wait_when_verification_disabled(
    tunnel_common_module,
):
    notifications = []
    url = "https://instant-tunnel.trycloudflare.com"
    helper = make_helper(tunnel_common_module, notifications, url)
    helper.ready_probe = lambda candidate: False
    helper.ready_timeout = 0

    assert helper.start() == url
    assert [notification["event"] for notification in notifications] == [
        "creating_tunnel",
        "tunnel_url",
    ]
