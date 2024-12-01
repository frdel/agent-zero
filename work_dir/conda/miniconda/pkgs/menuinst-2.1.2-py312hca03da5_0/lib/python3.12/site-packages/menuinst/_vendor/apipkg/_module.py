from __future__ import annotations

import sys
import threading
from types import ModuleType
from typing import Any
from typing import Callable
from typing import cast
from typing import Iterable

from ._importing import _py_abspath
from ._importing import importobj
from ._syncronized import _synchronized
from menuinst._vendor.apipkg import AliasModule


class ApiModule(ModuleType):
    """the magical lazy-loading module standing"""

    def __docget(self) -> str | None:
        try:
            return self.__doc
        except AttributeError:
            if "__doc__" in self.__map__:
                return cast(str, self.__makeattr("__doc__"))
            else:
                return None

    def __docset(self, value: str) -> None:
        self.__doc = value

    __doc__ = property(__docget, __docset)  # type: ignore
    __map__: dict[str, tuple[str, str]]

    def __init__(
        self,
        name: str,
        importspec: dict[str, Any],
        implprefix: str | None = None,
        attr: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name)
        self.__name__ = name
        self.__all__ = [x for x in importspec if x != "__onfirstaccess__"]
        self.__map__ = {}
        self.__implprefix__ = implprefix or name
        if attr:
            for name, val in attr.items():
                setattr(self, name, val)
        for name, importspec in importspec.items():
            if isinstance(importspec, dict):
                subname = f"{self.__name__}.{name}"
                apimod = ApiModule(subname, importspec, implprefix)
                sys.modules[subname] = apimod
                setattr(self, name, apimod)
            else:
                parts = importspec.split(":")
                modpath = parts.pop(0)
                attrname = parts and parts[0] or ""
                if modpath[0] == ".":
                    modpath = implprefix + modpath

                if not attrname:
                    subname = f"{self.__name__}.{name}"
                    apimod = AliasModule(subname, modpath)
                    sys.modules[subname] = apimod
                    if "." not in name:
                        setattr(self, name, apimod)
                else:
                    self.__map__[name] = (modpath, attrname)

    def __repr__(self):
        repr_list = [f"<ApiModule {self.__name__!r}"]
        if hasattr(self, "__version__"):
            repr_list.append(f" version={self.__version__!r}")
        if hasattr(self, "__file__"):
            repr_list.append(f" from {self.__file__!r}")
        repr_list.append(">")
        return "".join(repr_list)

    @_synchronized
    def __makeattr(self, name, isgetattr=False):
        """lazily compute value for name or raise AttributeError if unknown."""
        target = None
        if "__onfirstaccess__" in self.__map__:
            target = self.__map__.pop("__onfirstaccess__")
            fn = cast(Callable[[], None], importobj(*target))
            fn()
        try:
            modpath, attrname = self.__map__[name]
        except KeyError:
            # __getattr__ is called when the attribute does not exist, but it may have
            # been set by the onfirstaccess call above. Infinite recursion is not
            # possible as __onfirstaccess__ is removed before the call (unless the call
            # adds __onfirstaccess__ to __map__ explicitly, which is not our problem)
            if target is not None and name != "__onfirstaccess__":
                return getattr(self, name)
            # Attribute may also have been set during a concurrent call to __getattr__
            # which executed after this call was already waiting on the lock. Check
            # for a recently set attribute while avoiding infinite recursion:
            # * Don't call __getattribute__ if __makeattr was called from a data
            #   descriptor such as the __doc__ or __dict__ properties, since data
            #   descriptors are called as part of object.__getattribute__
            # * Only call __getattribute__ if there is a possibility something has set
            #   the attribute we're looking for since __getattr__ was called
            if threading is not None and isgetattr:
                return super().__getattribute__(name)
            raise AttributeError(name)
        else:
            result = importobj(modpath, attrname)
            setattr(self, name, result)
            # in a recursive-import situation a double-del can happen
            self.__map__.pop(name, None)
            return result

    def __getattr__(self, name):
        return self.__makeattr(name, isgetattr=True)

    def __dir__(self) -> Iterable[str]:
        yield from super().__dir__()
        yield from self.__map__

    @property
    def __dict__(self) -> dict[str, Any]:  # type: ignore
        # force all the content of the module
        # to be loaded when __dict__ is read
        dictdescr = ModuleType.__dict__["__dict__"]  # type: ignore
        ns: dict[str, Any] = dictdescr.__get__(self)
        if ns is not None:
            hasattr(self, "some")
            for name in self.__all__:
                try:
                    self.__makeattr(name)
                except AttributeError:
                    pass
        return ns


_PRESERVED_MODULE_ATTRS = {
    "__file__",
    "__version__",
    "__loader__",
    "__path__",
    "__package__",
    "__doc__",
    "__spec__",
    "__dict__",
}


def _initpkg(mod: ModuleType | None, pkgname, exportdefs, attr=None) -> ApiModule:
    """Helper for initpkg.

    Python 3.3+ uses finer grained locking for imports, and checks sys.modules before
    acquiring the lock to avoid the overhead of the fine-grained locking. This
    introduces a race condition when a module is imported by multiple threads
    concurrently - some threads will see the initial module and some the replacement
    ApiModule. We avoid this by updating the existing module in-place.

    """
    if mod is None:
        d = {"__file__": None, "__spec__": None}
        d.update(attr)
        mod = ApiModule(pkgname, exportdefs, implprefix=pkgname, attr=d)
        sys.modules[pkgname] = mod
        return mod
    else:
        f = getattr(mod, "__file__", None)
        if f:
            f = _py_abspath(f)
        mod.__file__ = f
        if hasattr(mod, "__path__"):
            mod.__path__ = [_py_abspath(p) for p in mod.__path__]
        if "__doc__" in exportdefs and hasattr(mod, "__doc__"):
            del mod.__doc__
        for name in dir(mod):
            if name not in _PRESERVED_MODULE_ATTRS:
                delattr(mod, name)

        # Updating class of existing module as per importlib.util.LazyLoader
        mod.__class__ = ApiModule
        apimod = cast(ApiModule, mod)
        ApiModule.__init__(apimod, pkgname, exportdefs, implprefix=pkgname, attr=attr)
        return apimod
