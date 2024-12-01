"""
"""

import os
from logging import basicConfig, getLogger

from .api import _install_adapter as install

try:
    from ._version import __version__
except ImportError:
    __version__ = "dev"

log = getLogger(__name__)
if os.environ.get("MENUINST_DEBUG"):
    basicConfig(level="DEBUG")

__all__ = ["install", "__version__"]


# Compatibility forwarders for menuinst v1.x (Windows only)
if os.name == "nt":
    from ._vendor.apipkg import initpkg

    initpkg(
        __name__,
        exportdefs={
            "win32": {
                "dirs_src": "menuinst.platforms.win_utils.knownfolders:dirs_src",
            },
            "knownfolders": {
                "get_folder_path": "menuinst.platforms.win_utils.knownfolders:get_folder_path",
                "FOLDERID": "menuinst.platforms.win_utils.knownfolders:FOLDERID",
            },
            "winshortcut": {
                "create_shortcut": "menuinst.platforms.win_utils.winshortcut:create_shortcut",
            },
            "win_elevate": {
                "runAsAdmin": "menuinst.platforms.win_utils.win_elevate:runAsAdmin",
                "isUserAdmin": "menuinst.platforms.win_utils.win_elevate:isUserAdmin",
            },
        },
        # Calling initpkg WILL CLEAR the 'menuinst' top-level namespace, and only then will add
        # the exportdefs contents! If we want to keep something defined in this module, we MUST
        # make sure it's added in the 'attr' dictionary below.
        attr={"__version__": __version__, "install": install},
    )
