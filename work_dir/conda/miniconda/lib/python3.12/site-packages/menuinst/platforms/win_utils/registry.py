r"""
Utilities for Windows Registry manipulation

Notes:

winreg.SetValue -> sets _keys_ with default ("") values
winreg.SetValueEx -> sets values with named contents

This is important when the argument has backslashes.
SetValue will process the backslashes into a path of keys
SetValueEx will create a value with name "path\with\keys"


Mnemonic: SetValueEx for "excalars" (scalars, named values)
"""

import ctypes
import winreg
from logging import getLogger

from ...utils import logged_run

log = getLogger(__name__)


def _reg_exe(*args, check=True):
    return logged_run(["reg.exe", *args, "/f"], check=check)


def register_file_extension(
    extension,
    identifier,
    command,
    icon=None,
    app_name=None,
    friendly_type_name=None,
    app_user_model_id=None,
    mode="user",
):
    """
    We want to achieve this. Entries ending in / denote keys; no trailing / means named value.
    If the item has a value attached to it, it's written after the : symbol.

    HKEY_*/ # current user or local machine
      Software/
        Classes/
          .<extension>/
            OpenWithProgids/
              <extension-handler>
          ...
          <extension-handler>/: "a description of the file being handled"
            DefaultIcon/: "path to the app icon"
            FriendlyAppName/: "Name of the program"
            AppUserModelID: "AUMI string"
            shell/
              open/: "Name of the program"
                icon: "path to the app icon"
                FriendlyAppName: "name of the program"
                command/: "the command to be executed when opening a file with this extension"
    """
    if mode == "system":
        key = "HKEY_LOCAL_MACHINE/Software/Classes"  # HKLM
    else:
        key = "HKEY_CURRENT_USER/Software/Classes"  # HKCU

    # First we associate an extension with a handler (presence of key is enough)
    regvalue(f"{key}/{extension}/OpenWithProgids/{identifier}", "")

    # Now we register the handler
    regvalue(f"{key}/{identifier}/@", f"{extension} {identifier} file")

    # Set the 'open' command
    regvalue(f"{key}/{identifier}/shell/open/command/@", command)
    if app_name:
        regvalue(f"{key}/{identifier}/shell/open/@", app_name)
        regvalue(f"{key}/{identifier}/FriendlyAppName/@", app_name)
        regvalue(f"{key}/{identifier}/shell/open/FriendlyAppName", app_name)

    if app_user_model_id:
        regvalue(f"{key}/{identifier}/AppUserModelID", app_user_model_id)

    if icon:
        # NOTE: This doesn't change the icon next in the Open With menu
        # This defaults to whatever the command executable is shipping
        regvalue(f"{key}/{identifier}/DefaultIcon/@", icon)
        regvalue(f"{key}/{identifier}/shell/open/Icon", icon)

    if friendly_type_name:
        # NOTE: Windows <10 requires the string in a PE file, but that's too
        # much work. We can just put the raw string here even if the docs say
        # otherwise.
        regvalue(f"{key}/{identifier}/FriendlyTypeName", friendly_type_name)

    # TODO: We can add contextual menu items too
    # via f"{handler_key}\shell\<Command Title>\command"


def unregister_file_extension(extension, identifier, mode="user"):
    root, root_str = (
        (winreg.HKEY_LOCAL_MACHINE, "HKLM")
        if mode == "system"
        else (winreg.HKEY_CURRENT_USER, "HKCU")
    )
    _reg_exe("delete", rf"{root_str}\Software\Classes\{identifier}", check=False)

    try:
        with winreg.OpenKey(
            root, rf"Software\Classes\{extension}\OpenWithProgids", 0, winreg.KEY_ALL_ACCESS
        ) as key:
            try:
                winreg.QueryValueEx(key, identifier)
            except FileNotFoundError:
                log.debug(
                    "Handler '%s' is not associated with extension '%s'", identifier, extension
                )
            else:
                winreg.DeleteValue(key, identifier)
    except Exception as exc:
        log.exception("Could not check key '%s' for deletion", extension, exc_info=exc)
        return False


def register_url_protocol(
    protocol,
    command,
    identifier=None,
    icon=None,
    app_name=None,
    app_user_model_id=None,
    mode="user",
):
    if mode == "system":
        key = f"HKEY_CLASSES_ROOT/{protocol}"
    else:
        key = f"HKEY_CURRENT_USER/Software/Classes/{protocol}"
    regvalue(f"{key}/@", f"URL:{protocol.title()}")
    regvalue(f"{key}/URL Protocol", "")
    regvalue(f"{key}/shell/open/command/@", command)
    if app_name:
        regvalue(f"{key}/shell/open/@", app_name)
        regvalue(f"{key}/FriendlyAppName/@", app_name)
        regvalue(f"{key}/shell/open/FriendlyAppName", app_name)
    if icon:
        regvalue(f"{key}/DefaultIcon/@", icon)
        regvalue(f"{key}/shell/open/Icon", icon)
    if app_user_model_id:
        regvalue(f"{key}/AppUserModelId", app_user_model_id)
    if identifier:
        # We add this one value for traceability; not required
        regvalue(f"{key}/_menuinst", identifier)


def unregister_url_protocol(protocol, identifier=None, mode="user"):
    if mode == "system":
        key_tuple = winreg.HKEY_CLASSES_ROOT, protocol
        key_str = rf"HKCR\{protocol}"
    else:
        key_tuple = winreg.HKEY_CURRENT_USER, rf"Software\Classes\{protocol}"
        key_str = rf"HKCU\Software\Classes\{protocol}"
    try:
        with winreg.OpenKey(*key_tuple) as key:
            value, _ = winreg.QueryValueEx(key, "_menuinst")
            delete = identifier is None or value == identifier
    except OSError as exc:
        log.exception("Could not check key %s for deletion", protocol, exc_info=exc)
        return

    if delete:
        _reg_exe("delete", key_str, check=False)


def regvalue(key, value, value_type=winreg.REG_SZ, raise_on_errors=True):
    """
    Convenience wrapper to set different types of registry values.

    For practical purposes we distinguish between three cases:

    - A key with no value (think of a directory with no contents).
      Use value = "".
    - A key with an unnamed value (think of a directory with a file 'index.html')
      Use a key with '@' as the last component.
    - A key with named values (think of non-index.html files in the directory)

    The first component of the key is the root, and must be one of the winreg.HKEY_*
    variable _names_ (their actual value will be fetched from winreg).

    Key must be at least three components long (root key, *key, @ or named value).
    """
    log.debug("Setting registry value %s = '%s'", key, value)
    key = original_key = key.replace("\\", "/").strip("/")
    root, *midkey, subkey, named_value = key.split("/")
    rootkey = getattr(winreg, root)
    access = winreg.KEY_SET_VALUE
    try:
        if named_value == "@":
            if midkey:
                winreg.CreateKey(rootkey, "\\".join(midkey))  # ensure it exists
            with winreg.OpenKey(rootkey, "\\".join(midkey), access=access) as key:
                winreg.SetValue(key, subkey, value_type, value)
        else:
            winreg.CreateKey(rootkey, "\\".join([*midkey, subkey]))  # ensure it exists
            with winreg.OpenKey(rootkey, "\\".join([*midkey, subkey]), access=access) as key:
                winreg.SetValueEx(key, named_value, 0, value_type, value)
    except OSError as exc:
        if raise_on_errors:
            raise
        log.warning("Could not set %s to %s", original_key, value, exc_info=exc)


def notify_shell_changes():
    """
    Needed to propagate registry changes without having to reboot.

    https://discuss.python.org/t/is-there-a-library-to-change-windows-10-default-program-icon/5846/2
    """
    shell32 = ctypes.OleDLL('shell32')
    shell32.SHChangeNotify.restype = None
    event = 0x08000000  # SHCNE_ASSOCCHANGED
    flags = 0x0000  # SHCNF_IDLIST
    shell32.SHChangeNotify(event, flags, None, None)
