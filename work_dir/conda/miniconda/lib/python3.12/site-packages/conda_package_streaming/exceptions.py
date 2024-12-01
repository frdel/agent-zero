import tarfile


class SafetyError(tarfile.TarError):
    def __init__(self, msg, *args, **kw):
        msg = f"Error with archive. {msg}"
        super().__init__(msg)


class CaseInsensitiveFileSystemError(OSError):
    def __init__(self):
        message = """\
Cannot extract package to a case-insensitive file system. Your install
destination does not differentiate between upper and lowercase characters, and
this breaks things. Try installing to a location that is case-sensitive. Windows
drives are usually the culprit here - can you install to a native Unix drive, or
turn on case sensitivity for this (Windows) location?
        """
        super().__init__(message)
