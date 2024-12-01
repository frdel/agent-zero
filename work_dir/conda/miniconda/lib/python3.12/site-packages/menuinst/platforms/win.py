"""
"""

import json
import os
import shutil
import warnings
from logging import getLogger
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional, Tuple

from ..utils import WinLex, logged_run, unlink
from .base import Menu, MenuItem
from .win_utils.knownfolders import folder_path as windows_folder_path
from .win_utils.knownfolders import windows_terminal_settings_files
from .win_utils.registry import (
    notify_shell_changes,
    register_file_extension,
    register_url_protocol,
    unregister_file_extension,
    unregister_url_protocol,
)

log = getLogger(__name__)


class WindowsMenu(Menu):
    def create(self) -> Tuple[os.PathLike]:
        log.debug("Creating %s", self.start_menu_location)
        self.start_menu_location.mkdir(parents=True, exist_ok=True)
        if self.quick_launch_location:
            self.quick_launch_location.mkdir(parents=True, exist_ok=True)
        if self.desktop_location:
            self.desktop_location.mkdir(parents=True, exist_ok=True)
        return (self.start_menu_location,)

    def remove(self) -> Tuple[os.PathLike]:
        # Only remove if the Start Menu directory is empty in case applications share a folder.
        menu_location = Path(self.start_menu_location)
        if menu_location.exists():
            try:
                # Check directory contents. If empty, it will raise StopIteration
                # and only in that case we delete the directory.
                next(menu_location.iterdir())
            except StopIteration:
                log.debug("Removing %s", self.start_menu_location)
                shutil.rmtree(self.start_menu_location, ignore_errors=True)
        return (self.start_menu_location,)

    @property
    def start_menu_location(self) -> Path:
        """
        On Windows we can create shortcuts in several places:

        - Start Menu
        - Desktop
        - Quick launch (only for user installs)

        In this property we only report the path to the Start menu.
        For other menus, check their respective properties.
        """
        return Path(windows_folder_path(self.mode, False, "start")) / self.render(self.name)

    @property
    def quick_launch_location(self) -> Path:
        if self.mode == "system":
            # TODO: Check if this is true?
            warnings.warn("Quick launch menus are not available for system level installs")
            return
        return Path(windows_folder_path(self.mode, False, "quicklaunch"))

    @property
    def desktop_location(self) -> Path:
        return Path(windows_folder_path(self.mode, False, "desktop"))

    @property
    def terminal_profile_locations(self) -> List[Path]:
        """Location of the Windows terminal profiles.

        The parent directory is used to check if Terminal is installed
        because the settings file is generated when Terminal is opened,
        not when it is installed.
        """
        if self.mode == "system":
            log.warning("Terminal profiles are not available for system level installs")
            return []
        return windows_terminal_settings_files(self.mode)

    @property
    def placeholders(self) -> Dict[str, str]:
        placeholders = super().placeholders
        placeholders.update(
            {
                "SCRIPTS_DIR": str(self.prefix / "Scripts"),
                "PYTHON": str(self.prefix / "python.exe"),
                "PYTHONW": str(self.prefix / "pythonw.exe"),
                "BASE_PYTHON": str(self.base_prefix / "python.exe"),
                "BASE_PYTHONW": str(self.base_prefix / "pythonw.exe"),
                "BIN_DIR": str(self.prefix / "Library" / "bin"),
                "SP_DIR": str(self._site_packages()),
                "ICON_EXT": "ico",
            }
        )
        return placeholders

    def _conda_exe_path_candidates(self):
        return (
            self.base_prefix / "_conda.exe",
            Path(os.environ.get("CONDA_EXE", r"C:\oops\a_file_that_does_not_exist")),
            self.base_prefix / "condabin" / "conda.bat",
            self.base_prefix / "bin" / "conda.bat",
            Path(os.environ.get("MAMBA_EXE", r"C:\oops\a_file_that_does_not_exist")),
            self.base_prefix / "condabin" / "micromamba.exe",
            self.base_prefix / "bin" / "micromamba.exe",
        )

    def render(
        self, value: Any, slug: bool = False, extra: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        We extend the render method here to replace forward slashes with backslashes.
        We ONLY do it if the string does not start with /, because it might
        be just a windows-style command-line flag (e.g. cmd /K something).

        This will not escape strings such as `/flag:something`, common
        in compiler stuff but we can assume such windows specific
        constructs will have their platform override, which is always an option.

        This is just a convenience for things like icon paths or Unix-like paths
        in the command key.
        """
        value = super().render(value, slug=slug, extra=extra)
        if hasattr(value, "replace") and "/" in value and value[0] != "/":
            value = value.replace("/", "\\")
        return value

    def _site_packages(self, prefix=None) -> Path:
        if prefix is None:
            prefix = self.prefix
        return self.prefix / "Lib" / "site-packages"

    def _paths(self) -> Tuple[Path]:
        return (self.start_menu_location,)


class WindowsMenuItem(MenuItem):
    @property
    def location(self) -> Path:
        """
        Path to the .lnk file placed in the Start Menu
        On Windows, menuinst can create up to three shortcuts (start menu, desktop, quick launch)
        This property only lists the one for start menu
        """
        return self.menu.start_menu_location / self._shortcut_filename()

    def create(self) -> Tuple[Path, ...]:
        from .win_utils.winshortcut import create_shortcut

        self._precreate()
        paths = self._paths()

        for path in paths:
            if not path.suffix == ".lnk":
                continue

            target_path, *arguments = self._process_command()
            working_dir = self.render_key("working_dir")
            if working_dir:
                Path(os.path.expandvars(working_dir)).mkdir(parents=True, exist_ok=True)
            # There are two possible interpretations of HOME on Windows:
            # `%USERPROFILE%` and `%HOMEDRIVE%%HOMEPATH%`.
            # Follow os.path.expanduser logic here, but keep the variables
            # so that Windows can resolve them at runtime in case the drives change.
            elif "USERPROFILE" in os.environ:
                working_dir = "%USERPROFILE%"
            else:
                working_dir = "%HOMEDRIVE%%HOMEPATH%"

            icon = self.render_key("icon") or ""

            # winshortcut is a windows-only C extension! create_shortcut has this API
            # Notice args must be passed as positional, no keywords allowed!
            # winshortcut.create_shortcut(path, description, filename, arguments="",
            #                             workdir=None, iconpath=None, iconindex=0, app_id="")
            if Path(path).exists():
                log.warning("Overwriting existing link at %s.", path)
            create_shortcut(
                target_path,
                self._shortcut_filename(ext=""),
                str(path),
                " ".join(arguments),
                working_dir,
                icon,
                0,
                self._app_user_model_id(),
            )

        for location in self.menu.terminal_profile_locations:
            self._add_remove_windows_terminal_profile(location, remove=False)
        changed_extensions = self._register_file_extensions()
        changed_protocols = self._register_url_protocols()
        if changed_extensions or changed_protocols:
            notify_shell_changes()

        return paths

    def remove(self) -> Tuple[Path, ...]:
        changed_extensions = self._unregister_file_extensions()
        changed_protocols = self._unregister_url_protocols()
        if changed_extensions or changed_protocols:
            notify_shell_changes()

        for location in self.menu.terminal_profile_locations:
            self._add_remove_windows_terminal_profile(location, remove=True)

        paths = self._paths()
        for path in paths:
            log.debug("Removing %s", path)
            unlink(path, missing_ok=True)

        return paths

    def _paths(self) -> Tuple[Path, ...]:
        paths = [self.location]
        extra_dirs = []
        if self.metadata["desktop"]:
            extra_dirs.append(self.menu.desktop_location)
        if self.metadata["quicklaunch"] and self.menu.quick_launch_location:
            extra_dirs.append(self.menu.quick_launch_location)

        if extra_dirs:
            paths += [directory / self._shortcut_filename() for directory in extra_dirs]

        if self.metadata["activate"]:
            # This is the accessory launcher script for cmd
            paths.append(self._path_for_script())

        return tuple(paths)

    def _shortcut_filename(self, ext: str = "lnk"):
        ext = f".{ext}" if ext else ""
        return f"{self.render_key('name', extra={})}{ext}"

    def _path_for_script(self) -> Path:
        return Path(self.menu.placeholders["MENU_DIR"]) / self._shortcut_filename("bat")

    def _precreate(self):
        precreate_code = self.render_key("precreate")
        if not precreate_code:
            return
        with NamedTemporaryFile(delete=False, mode="w") as tmp:
            tmp.write(precreate_code)
        system32 = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "system32"
        cmd = [
            str(system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
            f"\"start '{tmp.name}' -WindowStyle hidden\"",
        ]
        logged_run(cmd, check=True)
        os.unlink(tmp.name)

    def _command(self) -> str:
        lines = [
            "@ECHO OFF",
            ":: Script generated by conda/menuinst",
        ]
        precommand = self.render_key("precommand")
        if precommand:
            lines.append(precommand)
        if self.metadata["activate"]:
            conda_exe = self.menu.conda_exe
            if self.menu._is_micromamba(conda_exe):
                activate = "shell activate"
            else:
                activate = "shell.cmd.exe activate"
            activator = f'{self.menu.conda_exe} {activate} "{self.menu.prefix}"'
            lines += [
                "@SETLOCAL ENABLEDELAYEDEXPANSION",
                f'@FOR /F "usebackq tokens=*" %%i IN (`{activator}`) do set "ACTIVATOR=%%i"',
                "@CALL %ACTIVATOR%",
                ":: This below is the user command",
            ]

        lines.append(" ".join(WinLex.quote_args(self.render_key("command"))))

        return "\r\n".join(lines)

    def _write_script(self, script_path: Optional[os.PathLike] = None) -> Path:
        """
        This method generates the batch script that will be called by the shortcut
        """
        if script_path is None:
            script_path = self._path_for_script()
        else:
            script_path = Path(script_path)

        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(self._command())

        return script_path

    def _process_command(self, with_arg1=False) -> Tuple[str]:
        if self.metadata["activate"]:
            script = self._write_script()
            if self.metadata["terminal"]:
                command = ["cmd", "/D", "/K", f'"{script}"']
                if with_arg1:
                    command.append("%1")
            else:
                system32 = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "system32"
                arg1 = "%1 " if with_arg1 else ""
                # This is an UGLY hack to start the script in a hidden window
                # We use CMD to call PowerShell to call the BAT file
                # This flashes faster than Powershell -> BAT! Don't ask me why.
                command = [
                    f'"{system32 / "cmd.exe"}"',
                    "/D",
                    "/C",
                    "START",
                    "/MIN",
                    '""',
                    f'"{system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe"}"',
                    "-WindowStyle",
                    "hidden",
                    f"\"start '{script}' {arg1}-WindowStyle hidden\"",
                ]
            return command

        command = self.render_key("command")
        if with_arg1 and all("%1" not in arg for arg in command):
            command.append("%1")
        return WinLex.quote_args(command)

    def _add_remove_windows_terminal_profile(self, location: Path, remove: bool = False):
        """Add/remove the Windows Terminal profile.

        Windows Terminal is using the name of the profile to create a GUID,
        so the name will be used as the unique identifier to find existing profiles.

        If the Terminal app has never been opened, the settings file may not exist yet.
        Writing a minimal profile file will not break the application - Terminal will
        automatically generate the missing options and profiles without overwriting
        the profiles menuinst has created.
        """
        if not self.metadata.get("terminal_profile") or not location.parent.exists():
            return
        name = self.render_key("terminal_profile")

        settings = json.loads(location.read_text()) if location.exists() else {}

        index = -1
        for p, profile in enumerate(settings.get("profiles", {}).get("list", [])):
            if profile.get("name") == name:
                index = p
                break

        if remove:
            if index < 0:
                return
            del settings["profiles"]["list"][index]
        else:
            profile_data = {
                "commandline": " ".join(WinLex.quote_args(self.render_key("command"))),
                "name": name,
            }
            if self.metadata.get("icon"):
                profile_data["icon"] = self.render_key("icon")
            if self.metadata.get("working_dir"):
                profile_data["startingDirectory"] = self.render_key("working_dir")
            if index < 0:
                if "profiles" not in settings:
                    settings["profiles"] = {}
                if "list" not in settings["profiles"]:
                    settings["profiles"]["list"] = []
                settings["profiles"]["list"].append(profile_data)
            else:
                log.warning(f"Overwriting terminal profile for {name}.")
                settings["profiles"]["list"][index] = profile_data
        location.write_text(json.dumps(settings, indent=4))

    def _ftype_identifier(self, extension):
        identifier = self.render_key("name", slug=True)
        return f"{identifier}.AssocFile{extension}"

    def _register_file_extensions_cmd(self):
        """
        This function uses CMD's `assoc` and `ftype` commands.
        """
        extensions = self.metadata["file_extensions"]
        if not extensions:
            return
        command = " ".join(self._process_command())
        exts = list(dict.fromkeys([ext.lower() for ext in extensions]))
        for ext in exts:
            identifier = self._ftype_identifier(ext)
            self._cmd_ftype(identifier, command)
            self._cmd_assoc(ext, associate_to=identifier)

    def _unregister_file_extensions_cmd(self):
        """
        This function uses CMD's `assoc` and `ftype` commands.
        """
        extensions = self.metadata["file_extensions"]
        if not extensions:
            return
        exts = list(dict.fromkeys([ext.lower() for ext in extensions]))
        for ext in exts:
            identifier = self._ftype_identifier(ext)
            self._cmd_ftype(identifier)  # remove
            # TODO: Do we need to clean up the `assoc` mappings too?

    @staticmethod
    def _cmd_assoc(extension, associate_to=None, query=False, remove=False) -> CompletedProcess:
        "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/assoc"
        if sum([associate_to, query, remove]) != 1:
            raise ValueError("Only one of {associate_to, query, remove} must be set.")
        if not extension.startswith("."):
            raise ValueError("extension must startwith '.'")
        if associate_to:
            arg = f"{extension}={associate_to}"
        elif query:
            arg = extension
        elif remove:
            arg = f"{extension}="
        return logged_run(["cmd", "/D", "/C", f"assoc {arg}"], check=True)

    @staticmethod
    def _cmd_ftype(identifier, command=None, query=False, remove=False) -> CompletedProcess:
        "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/ftype"
        if sum([command, query, remove]) != 1:
            raise ValueError("Only one of {command, query, remove} must be set.")
        if command:
            arg = f"{identifier}={command}"
        elif query:
            arg = identifier
        elif remove:
            arg = f"{identifier}="
        return logged_run(["cmd", "/D", "/C", f"assoc {arg}"], check=True)

    def _register_file_extensions(self) -> bool:
        """WIP"""
        extensions = self.metadata["file_extensions"]
        if not extensions:
            return False

        command = " ".join(self._process_command(with_arg1=True))
        icon = self.render_key("icon")
        exts = list(dict.fromkeys([ext.lower() for ext in extensions]))
        for ext in exts:
            identifier = self._ftype_identifier(ext)
            register_file_extension(
                ext,
                identifier,
                command,
                icon=icon,
                app_name=self.render_key("name"),
                app_user_model_id=self._app_user_model_id(),
                mode=self.menu.mode,
            )
        return True

    def _unregister_file_extensions(self) -> bool:
        extensions = self.metadata["file_extensions"]
        if not extensions:
            return False

        exts = list(dict.fromkeys([ext.lower() for ext in extensions]))
        for ext in exts:
            identifier = self._ftype_identifier(ext)
            unregister_file_extension(ext, identifier, mode=self.menu.mode)
        return True

    def _register_url_protocols(self) -> bool:
        "See https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85)"  # noqa
        protocols = self.metadata["url_protocols"]
        if not protocols:
            return False
        command = " ".join(self._process_command(with_arg1=True))
        icon = self.render_key("icon")
        for protocol in protocols:
            identifier = self._ftype_identifier(protocol)
            register_url_protocol(
                protocol,
                command,
                identifier,
                icon=icon,
                app_name=self.render_key("name"),
                app_user_model_id=self._app_user_model_id(),
                mode=self.menu.mode,
            )
        return True

    def _unregister_url_protocols(self) -> bool:
        protocols = self.metadata["url_protocols"]
        if not protocols:
            return False
        for protocol in protocols:
            identifier = self._ftype_identifier(protocol)
            unregister_url_protocol(protocol, identifier, mode=self.menu.mode)
        return True

    def _app_user_model_id(self):
        aumi = self.render_key("app_user_model_id")
        if not aumi:
            return f"Menuinst.{self.render_key('name', slug=True).replace('.', '')}"[:128]
        return aumi
