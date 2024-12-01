from __future__ import annotations

from types import ModuleType

from ._importing import importobj


def AliasModule(modname: str, modpath: str, attrname: str | None = None) -> ModuleType:

    cached_obj: object | None = None

    def getmod() -> object:
        nonlocal cached_obj
        if cached_obj is None:
            cached_obj = importobj(modpath, attrname)
        return cached_obj

    x = modpath + ("." + attrname if attrname else "")
    repr_result = f"<AliasModule {modname!r} for {x!r}>"

    class AliasModule(ModuleType):
        def __repr__(self) -> str:
            return repr_result

        def __getattribute__(self, name: str) -> object:
            try:
                return getattr(getmod(), name)
            except ImportError:
                if modpath == "pytest" and attrname is None:
                    # hack for pylibs py.test
                    return None
                else:
                    raise

        def __setattr__(self, name: str, value: object) -> None:
            setattr(getmod(), name, value)

        def __delattr__(self, name: str) -> None:
            delattr(getmod(), name)

    return AliasModule(str(modname))
