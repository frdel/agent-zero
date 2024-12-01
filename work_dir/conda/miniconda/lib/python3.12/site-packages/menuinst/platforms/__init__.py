import sys
from typing import Tuple

from .base import Menu as BaseMenu
from .base import MenuItem as BaseMenuItem


def menu_api_for_platform(platform: str = sys.platform) -> Tuple[BaseMenu, BaseMenuItem]:
    if platform == "win32":
        from .win import WindowsMenu as Menu
        from .win import WindowsMenuItem as MenuItem

    elif platform == "darwin":
        from .osx import MacOSMenu as Menu
        from .osx import MacOSMenuItem as MenuItem

    elif platform.startswith("linux"):
        from .linux import LinuxMenu as Menu
        from .linux import LinuxMenuItem as MenuItem

    else:
        raise ValueError(f"platform {platform} is not supported")

    return Menu, MenuItem


Menu, MenuItem = menu_api_for_platform()
