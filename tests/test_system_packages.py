import os
from pathlib import Path
import subprocess

import pytest

from helpers import system_packages


@pytest.mark.parametrize("os_id", ["kali", "debian", "ubuntu"])
def test_runtime_apt_preserves_command_and_source_settings(tmp_path, monkeypatch, os_id):
    sources = (tmp_path / "sources.list", tmp_path / "kali.sources")
    contents = (
        "# Local mirror\ndeb https://mirror.example/kali kali-rolling main contrib\n",
        "Types: deb\nURIs: https://mirror.example/kali\nSuites: kali-rolling\nComponents: main\nSigned-By: /keyring.gpg\n",
    )
    for source, content in zip(sources, contents):
        source.write_text(content)
    monkeypatch.setattr(system_packages, "KALI_SOURCE_FILES", sources)
    monkeypatch.setattr(system_packages.platform, "freedesktop_os_release", lambda: {"ID": os_id})
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(system_packages.subprocess, "run", run)
    command = ["apt-get", "install", "-y", "python3-uno"]
    for _ in range(2):
        assert system_packages.run_runtime_apt(command, timeout=30).returncode == 0
        for source, content in zip(sources, contents):
            expected = content.replace("kali-rolling", "kali-last-snapshot") if os_id == "kali" else content
            assert source.read_text() == expected
        assert commands[-1] == command
    assert command == ["apt-get", "install", "-y", "python3-uno"]


def test_runtime_apt_propagates_source_write_errors(tmp_path, monkeypatch):
    source = tmp_path / "sources.list"
    source.write_text("deb https://mirror.example/kali kali-rolling main\n")
    monkeypatch.setattr(system_packages, "KALI_SOURCE_FILES", (source,))
    monkeypatch.setattr(system_packages.platform, "freedesktop_os_release", lambda: {"ID": "kali"})

    def fail_write(*args, **kwargs):
        raise PermissionError("source is read-only")

    monkeypatch.setattr(Path, "write_text", fail_write)
    monkeypatch.setattr(system_packages.subprocess, "run", lambda *args, **kwargs: pytest.fail("APT must not run"))
    with pytest.raises(PermissionError, match="source is read-only"):
        system_packages.run_runtime_apt(["apt-get", "install", "python3-gi-cairo"], timeout=30)


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_desktop_install_script_uses_compatible_architecture_packages(tmp_path, arch):
    root = Path(__file__).resolve().parents[1]
    script = (root / "docker/run/fs/ins/install_additional.sh").read_text()
    refresh = tmp_path / "refresh_xpra_index.sh"
    refresh.write_text((root / "plugins/_desktop/helpers/refresh_xpra_index.sh").read_text())
    script = script.replace("/git/agent-zero/plugins/_desktop/helpers/refresh_xpra_index.sh", str(refresh))
    for path in ("/etc/apt", "/usr/share/keyrings", "/var/lib/apt/lists"):
        (tmp_path / path.lstrip("/")).mkdir(parents=True)
        script = script.replace(path, str(tmp_path / path.lstrip("/")))
    sources = tmp_path / "etc/apt/sources.list"
    sources.write_text("deb https://mirror.example/kali kali-rolling main\n")
    (tmp_path / "etc/apt/sources.list.d").mkdir()
    log = tmp_path / "apt.log"
    stubs = r'''
apt-get() {
  [[ "$(<"$SIM_ROOT/etc/apt/sources.list")" == *kali-rolling* ]] || return 1
  [[ "$*" == *"Dir::Etc::sourceparts=-"* ]] || return 1
  if [[ "$*" == *"/xpra.sources"* ]]; then
    [[ "$*" == *'MetaKey=$(COMPONENT)/binary-$(ARCHITECTURE)/Packages.gz'* ]] || return 1
    [[ "$*" == *"APT::Get::List-Cleanup=false"* ]] || return 1
    [[ "$*" == *"APT::Update::Error-Mode=any"* ]] || return 1
  else
    [[ "$*" == *"Dir::Etc::sourcelist=$SIM_ROOT/etc/apt/a0-desktop.list"* ]] || return 1
  fi
  grep -q "signed-by=$SIM_ROOT/usr/share/keyrings/debian-archive-keyring.gpg" "$SIM_ROOT/etc/apt/a0-desktop.list" || return 1
  grep -q 'snapshot.debian.org/archive/debian/20260624T000000Z/' "$SIM_ROOT/etc/apt/a0-desktop.list" || return 1
  while [[ "$1" == -o ]]; do shift 2; done
  printf '%s\0' "$@" >> "$SIM_ROOT/apt.log"
  printf '\0' >> "$SIM_ROOT/apt.log"
  index="$SIM_ROOT/var/lib/apt/lists/xpra.org_dists_trixie_main_binary-${SIM_ARCH}_Packages.gz"
  if [[ "$1" == update && -f "$SIM_ROOT/etc/apt/sources.list.d/xpra.sources" ]]; then
    printf 'signed gzip index' > "$index.gz"
  elif [[ "$1" == indextargets ]]; then
    printf '%s\n' "$index.gz"
  elif [[ "$1" == install && "$*" == *xpra-common* ]]; then
    [[ "$(<"$index")" == 'signed gzip index' ]] || return 1
  fi
}
dpkg() { printf '%s\n' "$SIM_ARCH"; }
dpkg-query() {
  if [[ "$SIM_ARCH" == arm64 ]]; then
    printf 'install ok installed\n'
  else
    return 1
  fi
}
wget() { return 0; }
export -f apt-get
'''
    result = subprocess.run(
        ["bash", "-e", "-c", stubs + script], text=True, capture_output=True,
        env={**os.environ, "SIM_ROOT": str(tmp_path), "SIM_ARCH": arch},
    )
    assert result.returncode == 0, result.stderr
    commands = [command.split("\0") for command in log.read_text().split("\0\0") if command]
    installs = [command for command in commands if command[0] == "install"]
    assert len(installs) == 2
    for command in installs:
        assert not any(arg.startswith("python3=") for arg in command)
    assert f'xpra-html5={"19-r1-1" if arch == "amd64" else "21-r1-1"}' in installs[-1]
    assert "xpra-client=6.5.2-r0-1" in installs[-1]
    assert "python3-uno=4:26.2.4.2-1" in installs[-1]
    assert "--allow-downgrades" in installs[-1]
    assert "gir1.2-atk-1.0=2.60.3-1" in installs[-1]
    assert ("at-spi2-core=2.60.3-1" in installs[-1]) == (arch == "arm64")
    assert f"Architectures: {arch}\n" in (tmp_path / "etc/apt/sources.list.d/xpra.sources").read_text()
    assert f"arch={arch}" in (tmp_path / "etc/apt/a0-desktop.list").read_text()


@pytest.mark.parametrize("failure", ["update", "indextargets", "missing_index"])
def test_xpra_index_refresh_stops_on_failure(tmp_path, failure):
    script = Path(__file__).resolve().parents[1] / "plugins/_desktop/helpers/refresh_xpra_index.sh"
    stubs = r'''
apt-get() {
  while [[ "$1" == -o ]]; do shift 2; done
  [[ "$1" != "$SIM_FAILURE" ]] || return 42
  if [[ "$1" == indextargets ]]; then
    printf '%s\n' "$SIM_ROOT/missing_Packages.gz.gz"
  fi
}
export -f apt-get
'''
    result = subprocess.run(
        ["bash", "-ec", stubs + 'bash "$1" "$SIM_ROOT/xpra.sources"', "--", str(script)],
        text=True, capture_output=True,
        env={**os.environ, "SIM_ROOT": str(tmp_path), "SIM_FAILURE": failure},
    )
    assert result.returncode == (1 if failure == "missing_index" else 42)
    assert not (tmp_path / "missing_Packages.gz").exists()
