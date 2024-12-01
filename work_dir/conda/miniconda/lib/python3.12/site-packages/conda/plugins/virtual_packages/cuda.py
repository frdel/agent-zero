# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Detect CUDA version."""

import ctypes
import functools
import itertools
import multiprocessing
import os
import platform
from contextlib import suppress

from .. import CondaVirtualPackage, hookimpl


def cuda_version():
    """
    Attempt to detect the version of CUDA present in the operating system.

    On Windows and Linux, the CUDA library is installed by the NVIDIA
    driver package, and is typically found in the standard library path,
    rather than with the CUDA SDK (which is optional for running CUDA apps).

    On macOS, the CUDA library is only installed with the CUDA SDK, and
    might not be in the library path.

    Returns: version string (e.g., '9.2') or None if CUDA is not found.
    """
    if "CONDA_OVERRIDE_CUDA" in os.environ:
        return os.environ["CONDA_OVERRIDE_CUDA"].strip() or None

    # Do not inherit file descriptors and handles from the parent process.
    # The `fork` start method should be considered unsafe as it can lead to
    # crashes of the subprocess. The `spawn` start method is preferred.
    context = multiprocessing.get_context("spawn")
    queue = context.SimpleQueue()
    try:
        # Spawn a subprocess to detect the CUDA version
        detector = context.Process(
            target=_cuda_driver_version_detector_target,
            args=(queue,),
            name="CUDA driver version detector",
            daemon=True,
        )
        detector.start()
        detector.join(timeout=60.0)
    finally:
        # Always cleanup the subprocess
        detector.kill()  # requires Python 3.7+

    if queue.empty():
        return None

    result = queue.get()
    return result


@functools.lru_cache(maxsize=None)
def cached_cuda_version():
    """A cached version of the cuda detection system."""
    return cuda_version()


@hookimpl
def conda_virtual_packages():
    cuda_version = cached_cuda_version()
    if cuda_version is not None:
        yield CondaVirtualPackage("cuda", cuda_version, None)


def _cuda_driver_version_detector_target(queue):
    """
    Attempt to detect the version of CUDA present in the operating system in a
    subprocess.

    On Windows and Linux, the CUDA library is installed by the NVIDIA
    driver package, and is typically found in the standard library path,
    rather than with the CUDA SDK (which is optional for running CUDA apps).

    On macOS, the CUDA library is only installed with the CUDA SDK, and
    might not be in the library path.

    Returns: version string (e.g., '9.2') or None if CUDA is not found.
             The result is put in the queue rather than a return value.
    """
    # Platform-specific libcuda location
    system = platform.system()
    if system == "Darwin":
        lib_filenames = [
            "libcuda.1.dylib",  # check library path first
            "libcuda.dylib",
            "/usr/local/cuda/lib/libcuda.1.dylib",
            "/usr/local/cuda/lib/libcuda.dylib",
        ]
    elif system == "Linux":
        lib_filenames = [
            "libcuda.so",  # check library path first
            "/usr/lib64/nvidia/libcuda.so",  # RHEL/Centos/Fedora
            "/usr/lib/x86_64-linux-gnu/libcuda.so",  # Ubuntu
            "/usr/lib/wsl/lib/libcuda.so",  # WSL
        ]
        # Also add libraries with version suffix `.1`
        lib_filenames = list(
            itertools.chain.from_iterable((f"{lib}.1", lib) for lib in lib_filenames)
        )
    elif system == "Windows":
        bits = platform.architecture()[0].replace("bit", "")  # e.g. "64" or "32"
        lib_filenames = [f"nvcuda{bits}.dll", "nvcuda.dll"]
    else:
        queue.put(None)  # CUDA not available for other operating systems
        return

    # Open library
    if system == "Windows":
        dll = ctypes.windll
    else:
        dll = ctypes.cdll
    for lib_filename in lib_filenames:
        with suppress(Exception):
            libcuda = dll.LoadLibrary(lib_filename)
            break
    else:
        queue.put(None)
        return

    # Empty `CUDA_VISIBLE_DEVICES` can cause `cuInit()` returns `CUDA_ERROR_NO_DEVICE`
    # Invalid `CUDA_VISIBLE_DEVICES` can cause `cuInit()` returns `CUDA_ERROR_INVALID_DEVICE`
    # Unset this environment variable to avoid these errors
    os.environ.pop("CUDA_VISIBLE_DEVICES", None)

    # Get CUDA version
    try:
        cuInit = libcuda.cuInit
        flags = ctypes.c_uint(0)
        ret = cuInit(flags)
        if ret != 0:
            queue.put(None)
            return

        cuDriverGetVersion = libcuda.cuDriverGetVersion
        version_int = ctypes.c_int(0)
        ret = cuDriverGetVersion(ctypes.byref(version_int))
        if ret != 0:
            queue.put(None)
            return

        # Convert version integer to version string
        value = version_int.value
        queue.put(f"{value // 1000}.{(value % 1000) // 10}")
        return
    except Exception:
        queue.put(None)
        return
