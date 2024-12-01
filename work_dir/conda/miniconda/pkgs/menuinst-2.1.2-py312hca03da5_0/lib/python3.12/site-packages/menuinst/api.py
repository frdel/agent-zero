"""
"""

import json
import os
import sys
import warnings
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

from .platforms import Menu, MenuItem
from .utils import DEFAULT_BASE_PREFIX, DEFAULT_PREFIX, _UserOrSystem, elevate_as_needed

log = getLogger(__name__)


__all__ = [
    "install",
    "remove",
    "install_all",
    "remove_all",
]


def _load(
    metadata_or_path: Union[os.PathLike, dict],
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    _mode: _UserOrSystem = "user",
) -> Tuple[Menu, List[MenuItem]]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    if isinstance(metadata_or_path, (str, Path)):
        with open(metadata_or_path) as f:
            metadata = json.load(f)
    else:
        metadata = metadata_or_path
    menu = Menu(metadata["menu_name"], target_prefix, base_prefix, _mode)
    menu_items = [MenuItem(menu, item) for item in metadata["menu_items"]]
    return menu, menu_items


@elevate_as_needed
def install(
    metadata_or_path: Union[os.PathLike, dict],
    *,
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    _mode: _UserOrSystem = "user",
) -> List[os.PathLike]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    menu, menu_items = _load(metadata_or_path, target_prefix, base_prefix, _mode)
    if not any(item.enabled_for_platform() for item in menu_items):
        warnings.warn(f"Metadata for {menu.name} is not enabled for {sys.platform}")
        return ()

    paths = []
    paths += menu.create()
    for menu_item in menu_items:
        paths += menu_item.create()

    return paths


@elevate_as_needed
def remove(
    metadata_or_path: Union[os.PathLike, dict],
    *,
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    _mode: _UserOrSystem = "user",
) -> List[os.PathLike]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    menu, menu_items = _load(metadata_or_path, target_prefix, base_prefix, _mode)
    if not any(item.enabled_for_platform() for item in menu_items):
        warnings.warn(f"Metadata for {menu.name} is not enabled for {sys.platform}")
        return ()

    paths = []
    for menu_item in menu_items:
        paths += menu_item.remove()
    paths += menu.remove()

    return paths


@elevate_as_needed
def install_all(
    *,
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    filter: Union[Callable, None] = None,
    _mode: _UserOrSystem = "user",
) -> List[List[os.PathLike]]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    return _process_all(install, target_prefix, base_prefix, filter, _mode)


@elevate_as_needed
def remove_all(
    *,
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    filter: Union[Callable, None] = None,
    _mode: _UserOrSystem = "user",
) -> List[List[Union[str, os.PathLike]]]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    return _process_all(remove, target_prefix, base_prefix, filter, _mode)


def _process_all(
    function: Callable,
    target_prefix: Optional[os.PathLike] = None,
    base_prefix: Optional[os.PathLike] = None,
    filter: Union[Callable, None] = None,
    _mode: _UserOrSystem = "user",
) -> List[Any]:
    target_prefix = target_prefix or DEFAULT_PREFIX
    base_prefix = base_prefix or DEFAULT_BASE_PREFIX
    jsons = (Path(target_prefix) / "Menu").glob("*.json")
    results = []
    for path in jsons:
        if filter is not None and filter(path):
            results.append(function(path, target_prefix, base_prefix, _mode))
    return results


_api_remove = remove  # alias to prevent shadowing in the function below


def _install_adapter(
    path: os.PathLike, remove: bool = False, prefix: os.PathLike = DEFAULT_PREFIX, **kwargs
):
    """
    This function is only here as a legacy adapter for menuinst v1.x.
    Please use `menuinst.api` functions instead.
    """
    if os.name == "nt":
        path = path.replace("/", "\\")
    json_path = os.path.join(prefix, path)
    with open(json_path) as f:
        metadata = json.load(f)
    if "$id" not in metadata:  # old style JSON
        from ._legacy import install as _legacy_install

        if os.name == "nt":
            kwargs.setdefault("root_prefix", kwargs.pop("base_prefix", DEFAULT_BASE_PREFIX))
            if kwargs["root_prefix"] is None:
                kwargs["root_prefix"] = DEFAULT_BASE_PREFIX
            _legacy_install(json_path, remove=remove, prefix=prefix, **kwargs)
        else:
            log.warning(
                "menuinst._legacy is only supported on Windows. "
                "Switch to the new-style menu definitions "
                "for cross-platform compatibility."
            )
    else:
        # patch kwargs to reroute root_prefix to base_prefix
        kwargs.setdefault("base_prefix", kwargs.pop("root_prefix", DEFAULT_BASE_PREFIX))
        if kwargs["base_prefix"] is None:
            kwargs["base_prefix"] = DEFAULT_BASE_PREFIX
        if remove:
            _api_remove(metadata, target_prefix=prefix, **kwargs)
        else:
            install(metadata, target_prefix=prefix, **kwargs)
