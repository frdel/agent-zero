from __future__ import annotations

import abc


class AbstractBaseFormat(metaclass=abc.ABCMeta):
    @staticmethod
    @abc.abstractmethod
    def supported(fn):  # pragma: no cover
        return False

    @staticmethod
    @abc.abstractmethod
    def extract(fn, dest_dir, **kw):  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def create(prefix, file_list, out_fn, out_folder: str | None = None, **kw):  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_pkg_details(in_file):  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def list_contents(in_file, verbose=False, **kw):  # pragma: no cover
        raise NotImplementedError
