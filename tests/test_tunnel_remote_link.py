import io
import enum
import importlib
import os
import sys
import tarfile
import types
import zipfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeNotifyEvent(enum.Enum):
    DOWNLOADING = "downloading"
    DOWNLOAD_PROGRESS = "download_progress"
    DOWNLOAD_COMPLETE = "download_complete"
    CREATING_TUNNEL = "creating_tunnel"
    TUNNEL_URL = "tunnel_url"
    TUNNEL_STOPPED = "tunnel_stopped"
    ERROR = "error"
    INFO = "info"


class FakeConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeTunnel:
    def __init__(self, config):
        self.config = config
        self.tunnel_url = ""
        self.stopped = False
        self.notifications = []

    def start(self):
        self.tunnel_url = "https://example.test"
        return self.tunnel_url

    def stop(self):
        self.stopped = True
        return True

    def notify(self, event, message, data=None):
        self.notifications.append({
            "event": event.value if hasattr(event, "value") else event,
            "message": message,
            "data": data,
        })


class FakeNotifier:
    def subscribe(self, callback):
        self.callback = callback


def write_tar_archive(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            payload = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(payload))


def write_zip_archive(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


HELPER_MODULES = [
    "helpers.cli_tunnel",
    "helpers.cloudflare_tunnel",
    "helpers.microsoft_tunnel",
    "helpers.serveo_tunnel",
    "helpers.tailscale_tunnel",
    "helpers.tunnel_common",
    "helpers.tunnel_manager",
]


def remote_link_modules():
    return types.SimpleNamespace(
        cli=importlib.import_module("helpers.cli_tunnel"),
        microsoft=importlib.import_module("helpers.microsoft_tunnel"),
        tailscale=importlib.import_module("helpers.tailscale_tunnel"),
    )


@pytest.fixture()
def tunnel_manager_module(monkeypatch):
    fake_flaredantic = types.SimpleNamespace(
        FlareConfig=FakeConfig,
        FlareTunnel=FakeTunnel,
        MicrosoftConfig=FakeConfig,
        MicrosoftTunnel=FakeTunnel,
        NotifyData=object,
        NotifyEvent=FakeNotifyEvent,
        ServeoConfig=FakeConfig,
        ServeoTunnel=FakeTunnel,
        notifier=FakeNotifier(),
    )
    monkeypatch.setitem(sys.modules, "flaredantic", fake_flaredantic)
    helpers_package = sys.modules.get("helpers")
    for module_name in HELPER_MODULES:
        sys.modules.pop(module_name, None)
        if helpers_package and hasattr(helpers_package, module_name.rsplit(".", 1)[-1]):
            delattr(helpers_package, module_name.rsplit(".", 1)[-1])
    module = importlib.import_module("helpers.tunnel_manager")
    yield module
    for module_name in HELPER_MODULES:
        sys.modules.pop(module_name, None)
        if helpers_package and hasattr(helpers_package, module_name.rsplit(".", 1)[-1]):
            delattr(helpers_package, module_name.rsplit(".", 1)[-1])


def test_remote_link_provider_options_match_supported_remote_link_providers():
    html = (
        PROJECT_ROOT / "webui/components/settings/tunnel/tunnel-section.html"
    ).read_text(encoding="utf-8")

    assert html.count("<option value=") == 4
    assert "Remote Control" in html
    assert "Remote " + "Link" not in html
    assert "loginActionVisible" in html
    assert "loginActionTitle" in html
    assert (
        'class="microsoft-login-box" x-show="$store.tunnelStore.loginActionVisible"'
        in html
    )
    assert '<option value="cloudflared">Cloudflare Tunnel</option>' in html
    assert '<option value="tailscale">Tailscale</option>' in html
    assert '<option value="microsoft">Microsoft Dev Tunnels</option>' in html
    assert '<option value="serveo">Serveo</option>' in html
    assert '<option value="cloudflared">Cloudflare</option>' not in html
    assert "Cloudflare Tunnel is the quickest shareable URL" in html
    assert "Tailscale Funnel creates a public HTTPS URL" in html
    assert "approve sign-in or Funnel access" in html


def test_tunnel_provider_normalization_preserves_aliases(tunnel_manager_module):
    manager = tunnel_manager_module

    assert manager.normalize_provider("cloudflare") == "cloudflared"
    assert manager.normalize_provider("Cloudflare-Tunnel") == "cloudflared"
    assert manager.normalize_provider("tailscale-funnel") == "tailscale"

    with pytest.raises(ValueError, match="Unsupported remote control provider"):
        manager.normalize_provider("lantern")


def test_tailscale_cli_commands_are_wired(tunnel_manager_module):
    manager = tunnel_manager_module.TunnelManager()
    modules = remote_link_modules()

    tailscale = manager._create_tunnel(50001, "tailscale")

    assert tailscale.command == [
        "tailscale",
        "funnel",
        "--yes",
        "--https=443",
        "http://127.0.0.1:50001",
    ]
    assert tailscale.shutdown_command == [
        "tailscale",
        "funnel",
        "--yes",
        "--https=443",
        "http://127.0.0.1:50001",
        "off",
    ]
    assert tailscale.timeout == modules.tailscale.TAILSCALE_FUNNEL_TIMEOUT


def test_remote_link_providers_have_dedicated_helper_modules():
    helper_files = {
        "cloudflared": PROJECT_ROOT / "helpers/cloudflare_tunnel.py",
        "microsoft": PROJECT_ROOT / "helpers/microsoft_tunnel.py",
        "serveo": PROJECT_ROOT / "helpers/serveo_tunnel.py",
        "tailscale": PROJECT_ROOT / "helpers/tailscale_tunnel.py",
    }

    assert all(path.exists() for path in helper_files.values())


def test_microsoft_dev_tunnel_uses_unique_a0_tunnel_id(tunnel_manager_module):
    manager = tunnel_manager_module.TunnelManager()
    tunnel = manager._create_tunnel(50001, "microsoft")

    assert tunnel.start() == "https://example.test"

    config = tunnel.tunnel.config.kwargs
    assert config["tunnel_id"].startswith("agent-zero-")
    assert config["tunnel_id"] != "flaredantic"
    assert config["timeout"] == 120


def test_microsoft_dev_tunnel_id_can_be_overridden(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    monkeypatch.setenv("A0_MICROSOFT_DEV_TUNNEL_ID", "agent-zero-custom")

    assert modules.microsoft.default_microsoft_tunnel_id() == "agent-zero-custom"


def test_microsoft_dev_tunnel_timeout_error_is_enriched(
    tunnel_manager_module,
):
    modules = remote_link_modules()

    class FailingMicrosoftTunnel:
        def __init__(self, config):
            self.config = config

        def start(self):
            raise RuntimeError("Timeout waiting for Microsoft Dev Tunnels URL")

        def stop(self):
            return None

    modules.microsoft.AgentZeroMicrosoftTunnel = FailingMicrosoftTunnel
    tunnel = modules.microsoft.MicrosoftDevTunnel(50001)

    with pytest.raises(RuntimeError, match="global `flaredantic` tunnel-id collision"):
        tunnel.start()


def test_microsoft_dev_tunnel_emits_setup_progress_notifications(
    tunnel_manager_module,
):
    modules = remote_link_modules()
    config = FakeConfig(port=80, tunnel_id="agent-zero-test")
    tunnel = modules.microsoft.AgentZeroMicrosoftTunnel(config)
    commands = []

    def fake_run_cmd(args):
        commands.append(args)
        if args[0] == "show" or args[:2] == ["port", "show"]:
            return types.SimpleNamespace(returncode=1, stdout="missing")
        return types.SimpleNamespace(returncode=0, stdout="ok")

    tunnel._run_cmd = fake_run_cmd

    tunnel._ensure_tunnel()

    messages = [notification["message"] for notification in tunnel.notifications]
    assert messages == [
        "Checking Microsoft Dev Tunnel `agent-zero-test`...",
        "Creating Microsoft Dev Tunnel `agent-zero-test`...",
        "Checking Microsoft Dev Tunnel port 80...",
        "Creating Microsoft Dev Tunnel port 80...",
        "Microsoft Dev Tunnel setup is ready. Starting the secure host...",
    ]
    assert commands == [
        ["show", "agent-zero-test"],
        ["create", "agent-zero-test"],
        ["port", "show", "agent-zero-test", "-p", "80"],
        ["port", "create", "agent-zero-test", "-p", "80", "--protocol", "http"],
    ]


@pytest.mark.parametrize(
    ("provider", "expected_label"),
    [
        ("cloudflared", "Cloudflare Tunnel"),
        ("microsoft", "Microsoft Dev Tunnels"),
        ("serveo", "Serveo"),
    ],
)
def test_flaredantic_provider_helpers_emit_manager_notifications(
    tunnel_manager_module,
    monkeypatch,
    provider,
    expected_label,
):
    # This test exercises notification wiring, not the readiness wait.
    monkeypatch.setenv("A0_TUNNEL_READY_TIMEOUT", "0")
    manager = tunnel_manager_module.TunnelManager()
    tunnel = manager._create_tunnel(50001, provider)

    assert tunnel.start() == "https://example.test"

    assert manager.notifications[0] == {
        "event": "creating_tunnel",
        "message": f"Starting {expected_label} on port 50001...",
        "data": None,
    }
    assert manager.notifications[-1] == {
        "event": "tunnel_url",
        "message": f"{expected_label} URL is ready",
        "data": {"url": "https://example.test"},
    }


def test_zip_extraction_accepts_windows_exe_members(
    tunnel_manager_module,
    monkeypatch,
    tmp_path,
):
    modules = remote_link_modules()
    archive_path = tmp_path / "tailscale.zip"
    destination = tmp_path / "bin"
    write_zip_archive(archive_path, {"tailscale.exe": "binary"})
    monkeypatch.setattr(modules.cli.platform, "system", lambda: "Windows")

    extracted = modules.cli.extract_named_members_from_zip(
        archive_path,
        destination,
        {"tailscale"},
    )

    assert extracted == {"tailscale": destination / "tailscale.exe"}
    assert (destination / "tailscale.exe").read_text(encoding="utf-8") == "binary"


def test_tailscale_installs_runtime_binaries_from_static_archive(
    tunnel_manager_module,
    monkeypatch,
    tmp_path,
):
    modules = remote_link_modules()
    monkeypatch.setattr(modules.tailscale.shutil, "which", lambda binary: None)
    monkeypatch.setattr(modules.cli, "RUNTIME_BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_archive_url",
        lambda: "https://pkgs.tailscale.com/stable/tailscale_1.84.0_amd64.tgz",
    )

    def fake_download(url, destination, notify=None):
        write_tar_archive(
            destination,
            {
                "tailscale_1.84.0_amd64/tailscale": "#!/bin/sh\n",
                "tailscale_1.84.0_amd64/tailscaled": "#!/bin/sh\n",
            },
        )
        return destination

    monkeypatch.setattr(modules.cli, "download_file", fake_download)

    installed = Path(modules.tailscale.install_tailscale())

    assert installed == tmp_path / "bin" / "tailscale"
    assert (tmp_path / "bin" / "tailscaled").exists()
    assert os.access(tmp_path / "bin" / "tailscale", os.X_OK)
    assert os.access(tmp_path / "bin" / "tailscaled", os.X_OK)
    assert not (tmp_path / "bin" / "tailscale_1.84.0_amd64.tgz").exists()


def test_tailscale_installer_downloads_static_pair_when_system_daemon_is_missing(
    tunnel_manager_module,
    monkeypatch,
    tmp_path,
):
    modules = remote_link_modules()
    monkeypatch.setattr(
        modules.tailscale.shutil,
        "which",
        lambda binary: "/usr/bin/tailscale" if binary == "tailscale" else None,
    )
    monkeypatch.setattr(modules.cli, "RUNTIME_BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_archive_url",
        lambda: "https://pkgs.tailscale.com/stable/tailscale_1.84.0_amd64.tgz",
    )

    def fake_download(url, destination, notify=None):
        write_tar_archive(
            destination,
            {
                "tailscale_1.84.0_amd64/tailscale": "#!/bin/sh\n",
                "tailscale_1.84.0_amd64/tailscaled": "#!/bin/sh\n",
            },
        )
        return destination

    monkeypatch.setattr(modules.cli, "download_file", fake_download)

    assert modules.tailscale.install_tailscale() == str(tmp_path / "bin" / "tailscale")
    assert (tmp_path / "bin" / "tailscaled").exists()


def test_tailscale_static_package_url_is_discovered_from_official_listing(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    html = (
        '<a href="tailscale_1.84.0_arm64.tgz">arm</a>'
        '<a href="tailscale_1.84.0_amd64.tgz">amd64</a>'
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return html.encode("utf-8")

    monkeypatch.setattr(modules.tailscale, "tailscale_arch", lambda: "amd64")
    monkeypatch.setattr(
        modules.tailscale.urllib.request,
        "urlopen",
        lambda url, timeout=30: FakeResponse(),
    )

    assert (
        modules.tailscale.tailscale_archive_url()
        == "https://pkgs.tailscale.com/stable/tailscale_1.84.0_amd64.tgz"
    )


def test_tar_extraction_sanitizes_member_paths(
    tunnel_manager_module,
    tmp_path,
):
    modules = remote_link_modules()
    archive_path = tmp_path / "tailscale.tgz"
    destination = tmp_path / "safe"
    write_tar_archive(archive_path, {"../tailscale": "binary"})

    extracted = modules.cli.extract_named_members_from_tar(
        archive_path,
        destination,
        {"tailscale"},
    )

    assert extracted == {"tailscale": destination / "tailscale"}
    assert (destination / "tailscale").read_text(encoding="utf-8") == "binary"
    assert not (tmp_path / "tailscale").exists()


@pytest.mark.parametrize(
    ("provider", "module_name", "installer_name", "expected_message"),
    [
        ("tailscale", "tailscale", "install_tailscale", "tailscale download failed"),
    ],
)
def test_cli_provider_installer_failures_return_actionable_error(
    tunnel_manager_module,
    monkeypatch,
    provider,
    module_name,
    installer_name,
    expected_message,
):
    manager_module = tunnel_manager_module
    modules = remote_link_modules()
    manager = manager_module.TunnelManager()

    def fail_install(notify=None):
        raise RuntimeError(expected_message)

    monkeypatch.setattr(getattr(modules, module_name), installer_name, fail_install)

    assert manager.start_tunnel(port=50001, provider=provider) is None
    assert expected_message in manager.get_last_error()


def test_tailscale_preflight_starts_managed_daemon_then_runs_up_with_socket(
    tunnel_manager_module,
    monkeypatch,
    tmp_path,
):
    modules = remote_link_modules()
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "state"
    socket_path = runtime_dir / "tailscaled.sock"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tailscale = bin_dir / "tailscale"
    tailscaled = bin_dir / "tailscaled"
    tailscale.write_text("#!/bin/sh\n", encoding="utf-8")
    tailscaled.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(modules.tailscale, "TAILSCALE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(modules.tailscale, "TAILSCALE_STATE_DIR", state_dir)
    monkeypatch.setattr(modules.tailscale, "TAILSCALE_SOCKET_PATH", socket_path)
    monkeypatch.setattr(
        modules.tailscale,
        "TAILSCALE_DAEMON_LOG_PATH",
        runtime_dir / "tailscaled.log",
    )
    monkeypatch.setattr(
        modules.tailscale,
        "TAILSCALE_DAEMON_PID_PATH",
        runtime_dir / "tailscaled.pid",
    )
    status_results = iter([
        types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="failed to connect to local tailscaled",
        ),
        types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="failed to connect to local tailscaled",
        ),
        types.SimpleNamespace(returncode=1, stdout="Logged out.", stderr=""),
        types.SimpleNamespace(returncode=1, stdout="Logged out.", stderr=""),
        types.SimpleNamespace(
            returncode=0,
            stdout='{"BackendState": "Running"}',
            stderr="",
        ),
    ])
    status_calls = []

    def fake_status(binary_path, socket_path=None):
        status_calls.append((binary_path, socket_path))
        return next(status_results)

    monkeypatch.setattr(modules.tailscale, "tailscale_status", fake_status)
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_funnel_help",
        lambda binary_path, socket_path=None: types.SimpleNamespace(
            returncode=0,
            stdout="USAGE\n  tailscale funnel <target>",
            stderr="",
        ),
    )
    popen_commands = []

    class FakeProcess:
        def __init__(self, command, **kwargs):
            popen_commands.append(command)
            self.pid = 12345
            self.is_tailscale_up = command[0] == str(tailscale)
            self.stdout = iter(["Success.\n"]) if command[0] == str(tailscale) else None

        def poll(self):
            return 0 if self.is_tailscale_up else None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(modules.tailscale.subprocess, "Popen", FakeProcess)

    result = modules.tailscale.ensure_tailscale_ready(str(tailscale))

    assert result == {"command_prefix": ["--socket", str(socket_path)]}
    assert status_calls == [
        (str(tailscale), None),
        (str(tailscale), socket_path),
        (str(tailscale), socket_path),
        (str(tailscale), socket_path),
        (str(tailscale), socket_path),
    ]
    assert popen_commands == [
        [
            str(tailscaled),
            "--tun=userspace-networking",
            "--socket",
            str(socket_path),
            "--statedir",
            str(state_dir),
            "--state",
            str(state_dir / "tailscaled.state"),
        ],
        [str(tailscale), "--socket", str(socket_path), "up"],
    ]


def test_tailscale_preflight_emits_login_url_from_tailscale_up(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_status",
        lambda binary_path, socket_path=None: types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="",
        ),
    )

    class FakeProcess:
        stdout = iter(
            [
                "To authenticate, visit:\n",
                "https://login.tailscale.com/a/abcdef\n",
            ]
        )

        def poll(self):
            return 1

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 1

    notifications = []
    monkeypatch.setattr(
        modules.tailscale.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(),
    )

    with pytest.raises(RuntimeError, match="joining this container to your tailnet"):
        modules.tailscale.ensure_tailscale_ready(
            "/tmp/tailscale",
            notify=lambda event, message, data=None: notifications.append(
                {"event": event.value, "message": message, "data": data}
            ),
        )

    assert notifications[0]["message"] == (
        "Tailscale needs this container to join your tailnet. Running `tailscale up` now..."
    )
    assert notifications[1] == {
        "event": "info",
        "message": (
            "Open the Tailscale login link and approve this container. "
            "Agent Zero will continue when Tailscale finishes setup."
        ),
        "data": {
            "provider": "tailscale",
            "url": "https://login.tailscale.com/a/abcdef",
        },
    }


def test_tailscale_preflight_runs_up_then_accepts_running_status(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    status_results = iter([
        types.SimpleNamespace(returncode=1, stdout="", stderr="not logged in"),
        types.SimpleNamespace(
            returncode=0,
            stdout='{"BackendState": "Running"}',
            stderr="",
        ),
    ])
    notifications = []

    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_status",
        lambda binary_path, socket_path=None: next(status_results),
    )
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_funnel_help",
        lambda binary_path, socket_path=None: types.SimpleNamespace(
            returncode=0,
            stdout="USAGE\n  tailscale funnel <target>",
            stderr="",
        ),
    )

    class FakeProcess:
        stdout = iter(["Success.\n"])

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        modules.tailscale.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(),
    )

    modules.tailscale.ensure_tailscale_ready(
        "/tmp/tailscale",
        notify=lambda event, message, data=None: notifications.append(
            {"event": event.value, "message": message, "data": data}
        ),
    )

    assert notifications[-1] == {
        "event": "info",
        "message": "Tailscale setup completed. Checking the tailnet connection...",
        "data": None,
    }


def test_tailscale_preflight_rejects_clients_without_funnel(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_status",
        lambda binary_path, socket_path=None: types.SimpleNamespace(
            returncode=0,
            stdout='{"BackendState": "Running"}',
            stderr="",
        ),
    )
    monkeypatch.setattr(
        modules.tailscale,
        "tailscale_funnel_help",
        lambda binary_path, socket_path=None: types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="unknown command: funnel",
        ),
    )

    with pytest.raises(RuntimeError, match="does not support `tailscale funnel`"):
        modules.tailscale.ensure_tailscale_ready("/tmp/tailscale")


def test_tailscale_funnel_command_surfaces_approval_url(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    popen_commands = []
    notifications = []
    monkeypatch.setattr(
        modules.tailscale,
        "install_tailscale",
        lambda notify=None: "/tmp/tailscale",
    )
    monkeypatch.setattr(
        modules.tailscale,
        "ensure_tailscale_ready",
        lambda binary_path, notify=None: {
            "command_prefix": ["--socket", "/tmp/tailscaled.sock"]
        },
    )

    class FakeProcess:
        def __init__(self, command, **kwargs):
            popen_commands.append(command)
            self.stdout = iter([
                "Visit https://login.tailscale.com/a/funnel-approval to enable Funnel\n",
                "Available on the internet:\n",
                "https://agent-zero.example.ts.net\n",
            ])

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(modules.cli.subprocess, "Popen", FakeProcess)

    tunnel = modules.tailscale.TailscaleTunnel(
        50001,
        notify=lambda event, message, data=None: notifications.append({
            "event": event.value,
            "message": message,
            "data": data,
        }),
    )

    assert tunnel.start() == "https://agent-zero.example.ts.net"
    assert popen_commands == [
        [
            "/tmp/tailscale",
            "--socket",
            "/tmp/tailscaled.sock",
            "funnel",
            "--yes",
            "--https=443",
            "http://127.0.0.1:50001",
        ]
    ]
    assert {
        "event": "info",
        "message": (
            "Open the Tailscale approval link to finish sign-in or enable Funnel. "
            "Agent Zero will continue when Tailscale reports the public URL."
        ),
        "data": {
            "provider": "tailscale",
            "url": "https://login.tailscale.com/a/funnel-approval",
        },
    } in notifications
    assert notifications[-1] == {
        "event": "tunnel_url",
        "message": "Tailscale Funnel URL is ready",
        "data": {"url": "https://agent-zero.example.ts.net"},
    }


def test_cli_tunnel_preflight_prefix_is_used_for_start_and_shutdown(
    tunnel_manager_module,
    monkeypatch,
):
    modules = remote_link_modules()
    popen_commands = []
    run_commands = []

    class FakeProcess:
        def __init__(self, command, **kwargs):
            popen_commands.append(command)
            self.stdout = iter(["https://agent-zero.ts.net\n"])

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(modules.cli.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(
        modules.cli.subprocess,
        "run",
        lambda command, **kwargs: run_commands.append(command)
        or types.SimpleNamespace(returncode=0),
    )

    tunnel = modules.cli.CliTunnelHelper(
        label="Tailscale Funnel",
        binary="tailscale",
        port=50001,
        command=["tailscale", "funnel", "--yes", "http://127.0.0.1:50001"],
        shutdown_command=[
            "tailscale",
            "funnel",
            "--yes",
            "http://127.0.0.1:50001",
            "off",
        ],
        url_pattern=modules.tailscale.TAILSCALE_URL_RE,
        missing_binary_message="missing",
        binary_resolver=lambda notify=None: "/tmp/tailscale",
        preflight=lambda binary_path, notify=None: {
            "command_prefix": ["--socket", "/tmp/tailscaled.sock"]
        },
    )

    assert tunnel.start() == "https://agent-zero.ts.net"
    tunnel.stop()

    assert popen_commands == [
        [
            "/tmp/tailscale",
            "--socket",
            "/tmp/tailscaled.sock",
            "funnel",
            "--yes",
            "http://127.0.0.1:50001",
        ]
    ]
    assert run_commands == [
        [
            "/tmp/tailscale",
            "--socket",
            "/tmp/tailscaled.sock",
            "funnel",
            "--yes",
            "http://127.0.0.1:50001",
            "off",
        ]
    ]
