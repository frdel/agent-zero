""" """

import os
import shlex
import shutil
import time
from configparser import ConfigParser
from logging import getLogger
from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, Tuple
from xml.etree import ElementTree

from ..utils import UnixLex, add_xml_child, indent_xml_tree, logged_run, unlink
from .base import Menu, MenuItem, menuitem_defaults

log = getLogger(__name__)


class LinuxMenu(Menu):
    """
    Menus in Linux are governed by the freedesktop.org standards,
    spec'd here https://specifications.freedesktop.org/menu-spec/menu-spec-latest.html

    menuinst will populate the relevant XML config and create a .directory entry
    """

    _system_config_directory = Path("/etc/xdg/")
    _system_data_directory = Path("/usr/share")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.mode == "system":
            self.config_directory = self._system_config_directory
            self.data_directory = self._system_data_directory
        else:
            self.config_directory = Path(
                os.environ.get("XDG_CONFIG_HOME", "~/.config")
            ).expanduser()
            self.data_directory = Path(
                os.environ.get("XDG_DATA_HOME", "~/.local/share")
            ).expanduser()

        # XML Config paths
        self.system_menu_config_location = (
            self._system_config_directory / "menus" / "applications.menu"
        )
        self.menu_config_location = self.config_directory / "menus" / "applications.menu"
        # .desktop / .directory paths
        self.directory_entry_location = (
            self.data_directory
            / "desktop-directories"
            / f"{self.render(self.name, slug=True)}.directory"
        )
        self.desktop_entries_location = self.data_directory / "applications"

    def create(self) -> Tuple[os.PathLike]:
        self._ensure_directories_exist()
        path = self._write_directory_entry()
        if self._is_valid_menu_file() and self._has_this_menu():
            return (path,)
        self._ensure_menu_file()
        self._add_this_menu()
        return (path,)

    def remove(self) -> Tuple[os.PathLike]:
        for fn in os.listdir(self.desktop_entries_location):
            if fn.startswith(f"{self.render(self.name, slug=True)}_"):
                # found one shortcut, so don't remove the name from menu
                return (self.directory_entry_location,)
        unlink(self.directory_entry_location, missing_ok=True)
        self._remove_this_menu()
        return (self.directory_entry_location,)

    @property
    def placeholders(self) -> Dict[str, str]:
        placeholders = super().placeholders
        placeholders["SP_DIR"] = str(self._site_packages())
        return placeholders

    def _ensure_directories_exist(self):
        paths = [
            self.config_directory / "menus",
            self.data_directory / "desktop-directories",
            self.data_directory / "applications",
        ]
        for path in paths:
            log.debug("Ensuring path %s exists", path)
            path.mkdir(parents=True, exist_ok=True)

    #
    # .directory stuff methods
    #

    def _write_directory_entry(self) -> str:
        lines = [
            "[Desktop Entry]",
            "Type=Directory",
            "Encoding=UTF-8",
            f"Name={self.render(self.name)}",
        ]
        log.debug("Writing directory entry at %s", self.directory_entry_location)
        with open(self.directory_entry_location, "w") as f:
            f.write("\n".join(lines))

        return self.directory_entry_location

    #
    # XML config stuff methods
    #

    def _remove_this_menu(self):
        log.debug(
            "Editing %s to remove %s config", self.menu_config_location, self.render(self.name)
        )
        tree = ElementTree.parse(self.menu_config_location)
        root = tree.getroot()
        for elt in root.findall("Menu"):
            if elt.find("Name").text == self.render(self.name):
                root.remove(elt)
        self._write_menu_file(tree)

    def _has_this_menu(self) -> bool:
        root = ElementTree.parse(self.menu_config_location).getroot()
        return any(e.text == self.render(self.name) for e in root.findall("Menu/Name"))

    def _add_this_menu(self):
        log.debug("Editing %s to add %s config", self.menu_config_location, self.render(self.name))
        tree = ElementTree.parse(self.menu_config_location)
        root = tree.getroot()
        menu_elt = add_xml_child(root, "Menu")
        add_xml_child(menu_elt, "Name", self.render(self.name))
        add_xml_child(menu_elt, "Directory", f"{self.render(self.name, slug=True)}.directory")
        inc_elt = add_xml_child(menu_elt, "Include")
        add_xml_child(inc_elt, "Category", self.render(self.name))
        self._write_menu_file(tree)

    def _is_valid_menu_file(self) -> bool:
        try:
            root = ElementTree.parse(self.menu_config_location).getroot()
            return root is not None and root.tag == "Menu"
        except Exception:
            return False

    def _write_menu_file(self, tree: ElementTree):
        log.debug("Writing %s", self.menu_config_location)
        indent_xml_tree(tree.getroot())  # inplace!
        with open(self.menu_config_location, "wb") as f:
            f.write(b'<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"\n')
            f.write(b' "http://standards.freedesktop.org/menu-spec/menu-1.0.dtd">\n')
            tree.write(f)
            f.write(b"\n")

    def _ensure_menu_file(self):
        # ensure any existing version is a file
        if self.menu_config_location.exists() and not self.menu_config_location.is_file():
            raise RuntimeError(f"Menu config location {self.menu_config_location} is not a file!")
            # shutil.rmtree(self.menu_config_location)

        # ensure any existing file is actually a menu file
        if self.menu_config_location.is_file():
            # make a backup of the menu file to be edited
            cur_time = time.strftime("%Y-%m-%d_%Hh%Mm%S")
            backup_menu_file = f"{self.menu_config_location}.{cur_time}"
            shutil.copyfile(self.menu_config_location, backup_menu_file)

            if not self._is_valid_menu_file():
                os.remove(self.menu_config_location)
        else:
            self._new_menu_file()

    def _new_menu_file(self):
        log.debug("Creating %s", self.menu_config_location)
        with open(self.menu_config_location, "w") as f:
            f.write("<Menu><Name>Applications</Name>")
            if self.mode == "user":
                f.write(f'<MergeFile type="parent">{self.system_menu_config_location}</MergeFile>')
            f.write("</Menu>\n")

    def _paths(self) -> Tuple[str]:
        return (self.directory_entry_location,)


class LinuxMenuItem(MenuItem):
    @property
    def location(self) -> Path:
        menu_prefix = self.render(self.menu.name, slug=True, extra={})
        # TODO: filename should conform to D-Bus well known name conventions
        # https://specifications.freedesktop.org/desktop-entry-spec/latest/ar01s02.html
        filename = f"{menu_prefix}_{self.render_key('name', slug=True, extra={})}.desktop"
        return self.menu.desktop_entries_location / filename

    def create(self) -> Iterable[os.PathLike]:
        log.debug("Creating %s", self.location)
        self._precreate()
        self._write_desktop_file()
        self._maybe_register_mime_types(register=True)
        self._update_desktop_database()
        return self._paths()

    def remove(self) -> Iterable[os.PathLike]:
        paths = self._paths()
        self._maybe_register_mime_types(register=False)
        for path in paths:
            log.debug("Removing %s", path)
            unlink(path, missing_ok=True)
        self._update_desktop_database()
        return paths

    def _update_desktop_database(self):
        exe = shutil.which("update-desktop-database")
        if exe:
            logged_run(
                [exe, str(self.menu.desktop_entries_location)],
                check=False,
            )

    def _command(self) -> str:
        parts = []
        precommand = self.render_key("precommand")
        if precommand:
            parts.append(precommand)
        if self.metadata["activate"]:
            conda_exe = self.menu.conda_exe
            if self.menu._is_micromamba(conda_exe):
                activate = "shell activate"
            else:
                activate = "shell.bash activate"
            parts.append(f'eval "$("{conda_exe}" {activate} "{self.menu.prefix}")"')
        parts.append(" ".join(UnixLex.quote_args(self.render_key("command"))))
        return "bash -c " + shlex.quote(" && ".join(parts))

    def _write_desktop_file(self):
        if self.location.exists():
            log.warning("Overwriting existing file at %s.", self.location)

        lines = [
            "[Desktop Entry]",
            "Type=Application",
            "Encoding=UTF-8",
            f'Name={self.render_key("name")}',
            f"Exec={self._command()}",
            f'Terminal={str(self.render_key("terminal")).lower()}',
        ]

        icon = self.render_key("icon")
        if icon:
            lines.append(f'Icon={self.render_key("icon")}')

        description = self.render_key("description")
        if description:
            lines.append(f'Comment={self.render_key("description")}')

        working_dir = self.render_key("working_dir")
        if working_dir:
            Path(os.path.expandvars(working_dir)).mkdir(parents=True, exist_ok=True)
            lines.append(f"Path={working_dir}")

        for key in menuitem_defaults["platforms"]["linux"]:
            if key in (*menuitem_defaults, "glob_patterns"):
                continue
            value = self.render_key(key)
            if value is None:
                continue
            if isinstance(value, bool):
                value = str(value).lower()
            elif isinstance(value, (list, tuple)):
                value = ";".join(value) + ";"
            lines.append(f"{key}={value}")

        with open(self.location, "w") as f:
            f.write("\n".join(lines))
            f.write("\n")

    def _maybe_register_mime_types(self, register=True):
        mime_types = self.render_key("MimeType")
        if not mime_types:
            return
        self._register_mime_types(mime_types, register=register)

    def _register_mime_types(self, mime_types: Iterable[str], register: bool = True):
        glob_patterns = self.render_key("glob_patterns") or {}
        for mime_type in mime_types:
            glob_pattern = glob_patterns.get(mime_type)
            if glob_pattern:
                self._glob_pattern_for_mime_type(mime_type, glob_pattern, install=register)

        mimeapps = self.menu.config_directory / "mimeapps.list"
        if register:
            config = ConfigParser(default_section=None)
            if mimeapps.is_file():
                config.read(mimeapps)
            log.debug("Registering %s to %s...", mime_types, mimeapps)
            if "Default Applications" not in config.sections():
                config.add_section("Default Applications")
            if "Added Associations" not in config.sections():
                config.add_section("Added Associations")
            defaults = config["Default Applications"]
            added = config["Added Associations"]
            for mime_type in mime_types:
                if mime_type not in defaults:
                    # Do not override existing defaults
                    defaults[mime_type] = self.location.name
                if mime_type in added and self.location.name not in added[mime_type]:
                    added[mime_type] = f"{added[mime_type]};{self.location.name}"
                else:
                    added[mime_type] = self.location.name
            with open(mimeapps, "w") as f:
                config.write(f, space_around_delimiters=False)
        elif mimeapps.is_file():
            # Remove entries
            config = ConfigParser(default_section=None)
            config.read(mimeapps)
            log.debug("Deregistering %s from %s...", mime_types, mimeapps)
            for section_name in "Default Applications", "Added Associations":
                if section_name not in config.sections():
                    continue
                section = config[section_name]
                for mimetype, desktop_files in section.items():
                    if self.location.name == desktop_files:
                        section.pop(mimetype)
                    elif self.location.name in desktop_files.split(";"):
                        section[mimetype] = ";".join(
                            [x for x in desktop_files.split(";") if x != self.location.name]
                        )
                if not section.keys():
                    config.remove_section(section_name)
            with open(mimeapps, "w") as f:
                config.write(f, space_around_delimiters=False)

        update_mime_database = shutil.which("update-mime-database")
        if update_mime_database:
            logged_run(
                [update_mime_database, "-V", self.menu.data_directory / "mime"],
                check=False,
            )

    def _xml_path_for_mime_type(self, mime_type: str) -> Tuple[Path, bool]:
        basename = mime_type.replace("/", "-")
        xml_files = list(
            (self.menu.data_directory / "mime" / "applications").glob(f"*{basename}*.xml")
        )
        if xml_files:
            if len(xml_files) > 1:
                msg = "Found multiple files for MIME type %s: %s. Returning first."
                log.debug(msg, mime_type, xml_files)
            return xml_files[0], True
        return self.menu.data_directory / "mime" / "packages" / f"{basename}.xml", False

    def _glob_pattern_for_mime_type(
        self,
        mime_type: str,
        glob_pattern: str,
        install: bool = True,
    ) -> Path:
        """
        See https://specifications.freedesktop.org/mime-apps-spec/mime-apps-spec-latest.html
        for more information on the default locations.
        """
        xml_path, exists = self._xml_path_for_mime_type(mime_type)
        if exists:
            return xml_path

        # Write the XML that binds our current mime type to the glob pattern
        xmlns = "http://www.freedesktop.org/standards/shared-mime-info"
        mime_info = ElementTree.Element("mime-info", xmlns=xmlns)
        mime_type_tag = ElementTree.SubElement(mime_info, "mime-type", type=mime_type)
        ElementTree.SubElement(mime_type_tag, "glob", pattern=glob_pattern)
        descr = f"Custom MIME type {mime_type} for '{glob_pattern}' files (registered by menuinst)"
        ElementTree.SubElement(mime_type_tag, "comment").text = descr
        tree = ElementTree.ElementTree(mime_info)

        subcommand = "install" if install else "uninstall"
        # Install the XML file and register it as default for our app
        try:
            with TemporaryDirectory() as tmp:
                with open(os.path.join(tmp, os.path.basename(xml_path)), "wb") as f:
                    tree.write(f, encoding="UTF-8", xml_declaration=True)
                logged_run(
                    ["xdg-mime", subcommand, "--mode", self.menu.mode, "--novendor", f.name],
                    check=True,
                )
        except CalledProcessError:
            log.debug(
                "Could not un/register MIME type %s with xdg-mime. Writing to '%s' as a fallback.",
                mime_type,
                xml_path,
            )
            tree.write(xml_path, encoding="UTF-8", xml_declaration=True)

    def _paths(self) -> Iterable[os.PathLike]:
        paths = [self.location]
        mime_types = self.render_key("MimeType") or ()
        for mime in mime_types:
            xml_path, exists = self._xml_path_for_mime_type(mime)
            if exists and "registered by menuinst" in xml_path.read_text():
                paths.append(xml_path)
        return tuple(paths)
