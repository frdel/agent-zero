# Copyright 2019-2020 Lawrence Livermore National Security, LLC and other
# Archspec Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Detection of CPU microarchitectures"""
import collections
import os
import platform
import re
import struct
import subprocess
import warnings
from typing import Dict, List, Optional, Set, Tuple, Union

from ..vendor.cpuid.cpuid import CPUID
from .microarchitecture import TARGETS, Microarchitecture, generic_microarchitecture
from .schema import CPUID_JSON, TARGETS_JSON

#: Mapping from operating systems to chain of commands
#: to obtain a dictionary of raw info on the current cpu
INFO_FACTORY = collections.defaultdict(list)

#: Mapping from micro-architecture families (x86_64, ppc64le, etc.) to
#: functions checking the compatibility of the host with a given target
COMPATIBILITY_CHECKS = {}

# Constants for commonly used architectures
X86_64 = "x86_64"
AARCH64 = "aarch64"
PPC64LE = "ppc64le"
PPC64 = "ppc64"
RISCV64 = "riscv64"


def detection(operating_system: str):
    """Decorator to mark functions that are meant to return partial information on the current cpu.

    Args:
        operating_system: operating system where this function can be used.
    """

    def decorator(factory):
        INFO_FACTORY[operating_system].append(factory)
        return factory

    return decorator


def partial_uarch(
    name: str = "", vendor: str = "", features: Optional[Set[str]] = None, generation: int = 0
) -> Microarchitecture:
    """Construct a partial microarchitecture, from information gathered during system scan."""
    return Microarchitecture(
        name=name,
        parents=[],
        vendor=vendor,
        features=features or set(),
        compilers={},
        generation=generation,
    )


@detection(operating_system="Linux")
def proc_cpuinfo() -> Microarchitecture:
    """Returns a partial Microarchitecture, obtained from scanning ``/proc/cpuinfo``"""
    data = {}
    with open("/proc/cpuinfo") as file:  # pylint: disable=unspecified-encoding
        for line in file:
            key, separator, value = line.partition(":")

            # If there's no separator and info was already populated
            # according to what's written here:
            #
            # http://www.linfo.org/proc_cpuinfo.html
            #
            # we are on a blank line separating two cpus. Exit early as
            # we want to read just the first entry in /proc/cpuinfo
            if separator != ":" and data:
                break

            data[key.strip()] = value.strip()

    architecture = _machine()
    if architecture == X86_64:
        return partial_uarch(
            vendor=data.get("vendor_id", "generic"), features=_feature_set(data, key="flags")
        )

    if architecture == AARCH64:
        return partial_uarch(
            vendor=_canonicalize_aarch64_vendor(data),
            features=_feature_set(data, key="Features"),
        )

    if architecture in (PPC64LE, PPC64):
        generation_match = re.search(r"POWER(\d+)", data.get("cpu", ""))
        try:
            generation = int(generation_match.group(1))
        except AttributeError:
            # There might be no match under emulated environments. For instance
            # emulating a ppc64le with QEMU and Docker still reports the host
            # /proc/cpuinfo and not a Power
            generation = 0
        return partial_uarch(generation=generation)

    if architecture == RISCV64:
        if data.get("uarch") == "sifive,u74-mc":
            data["uarch"] = "u74mc"
        return partial_uarch(name=data.get("uarch", RISCV64))

    return generic_microarchitecture(architecture)


class CpuidInfoCollector:
    """Collects the information we need on the host CPU from cpuid"""

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.cpuid = CPUID()

        registers = self.cpuid.registers_for(**CPUID_JSON["vendor"]["input"])
        self.highest_basic_support = registers.eax
        self.vendor = struct.pack("III", registers.ebx, registers.edx, registers.ecx).decode(
            "utf-8"
        )

        registers = self.cpuid.registers_for(**CPUID_JSON["highest_extension_support"]["input"])
        self.highest_extension_support = registers.eax

        self.features = self._features()

    def _features(self):
        result = set()

        def check_features(data):
            registers = self.cpuid.registers_for(**data["input"])
            for feature_check in data["bits"]:
                current = getattr(registers, feature_check["register"])
                if self._is_bit_set(current, feature_check["bit"]):
                    result.add(feature_check["name"])

        for call_data in CPUID_JSON["flags"]:
            if call_data["input"]["eax"] > self.highest_basic_support:
                continue
            check_features(call_data)

        for call_data in CPUID_JSON["extension-flags"]:
            if call_data["input"]["eax"] > self.highest_extension_support:
                continue
            check_features(call_data)

        return result

    def _is_bit_set(self, register: int, bit: int) -> bool:
        mask = 1 << bit
        return register & mask > 0


@detection(operating_system="Windows")
def cpuid_info():
    """Returns a partial Microarchitecture, obtained from running the cpuid instruction"""
    architecture = _machine()
    if architecture == X86_64:
        data = CpuidInfoCollector()
        return partial_uarch(vendor=data.vendor, features=data.features)

    return generic_microarchitecture(architecture)


def _check_output(args, env):
    with subprocess.Popen(args, stdout=subprocess.PIPE, env=env) as proc:
        output = proc.communicate()[0]
    return str(output.decode("utf-8"))


WINDOWS_MAPPING = {
    "AMD64": "x86_64",
    "ARM64": "aarch64",
}


def _machine():
    """Return the machine architecture we are on"""
    operating_system = platform.system()

    # If we are not on Darwin or Windows, trust what Python tells us
    if operating_system not in ("Darwin", "Windows"):
        return platform.machine()

    # Normalize windows specific names
    if operating_system == "Windows":
        platform_machine = platform.machine()
        return WINDOWS_MAPPING.get(platform_machine, platform_machine)

    # On Darwin it might happen that we are on M1, but using an interpreter
    # built for x86_64. In that case "platform.machine() == 'x86_64'", so we
    # need to fix that.
    #
    # See: https://bugs.python.org/issue42704
    output = _check_output(
        ["sysctl", "-n", "machdep.cpu.brand_string"], env=_ensure_bin_usrbin_in_path()
    ).strip()

    if "Apple" in output:
        # Note that a native Python interpreter on Apple M1 would return
        # "arm64" instead of "aarch64". Here we normalize to the latter.
        return AARCH64

    return X86_64


@detection(operating_system="Darwin")
def sysctl_info() -> Microarchitecture:
    """Returns a raw info dictionary parsing the output of sysctl."""
    child_environment = _ensure_bin_usrbin_in_path()

    def sysctl(*args: str) -> str:
        return _check_output(["sysctl"] + list(args), env=child_environment).strip()

    if _machine() == X86_64:
        features = (
            f'{sysctl("-n", "machdep.cpu.features").lower()} '
            f'{sysctl("-n", "machdep.cpu.leaf7_features").lower()}'
        )
        features = set(features.split())

        # Flags detected on Darwin turned to their linux counterpart
        for darwin_flag, linux_flag in TARGETS_JSON["conversions"]["darwin_flags"].items():
            if darwin_flag in features:
                features.update(linux_flag.split())

        return partial_uarch(vendor=sysctl("-n", "machdep.cpu.vendor"), features=features)

    model = "unknown"
    model_str = sysctl("-n", "machdep.cpu.brand_string").lower()
    if "m2" in model_str:
        model = "m2"
    elif "m1" in model_str:
        model = "m1"
    elif "apple" in model_str:
        model = "m1"

    return partial_uarch(name=model, vendor="Apple")


def _ensure_bin_usrbin_in_path():
    # Make sure that /sbin and /usr/sbin are in PATH as sysctl is usually found there
    child_environment = dict(os.environ.items())
    search_paths = child_environment.get("PATH", "").split(os.pathsep)
    for additional_path in ("/sbin", "/usr/sbin"):
        if additional_path not in search_paths:
            search_paths.append(additional_path)
    child_environment["PATH"] = os.pathsep.join(search_paths)
    return child_environment


def _canonicalize_aarch64_vendor(data: Dict[str, str]) -> str:
    """Adjust the vendor field to make it human-readable"""
    if "CPU implementer" not in data:
        return "generic"

    # Mapping numeric codes to vendor (ARM). This list is a merge from
    # different sources:
    #
    # https://github.com/karelzak/util-linux/blob/master/sys-utils/lscpu-arm.c
    # https://developer.arm.com/docs/ddi0487/latest/arm-architecture-reference-manual-armv8-for-armv8-a-architecture-profile
    # https://github.com/gcc-mirror/gcc/blob/master/gcc/config/aarch64/aarch64-cores.def
    # https://patchwork.kernel.org/patch/10524949/
    arm_vendors = TARGETS_JSON["conversions"]["arm_vendors"]
    arm_code = data["CPU implementer"]
    return arm_vendors.get(arm_code, arm_code)


def _feature_set(data: Dict[str, str], key: str) -> Set[str]:
    return set(data.get(key, "").split())


def detected_info() -> Microarchitecture:
    """Returns a partial Microarchitecture with information on the CPU of the current host.

    This function calls all the viable factories one after the other until there's one that is
    able to produce the requested information. Falls-back to a generic microarchitecture, if none
    of the calls succeed.
    """
    # pylint: disable=broad-except
    for factory in INFO_FACTORY[platform.system()]:
        try:
            return factory()
        except Exception as exc:
            warnings.warn(str(exc))

    return generic_microarchitecture(_machine())


def compatible_microarchitectures(info: Microarchitecture) -> List[Microarchitecture]:
    """Returns an unordered list of known micro-architectures that are compatible with the
    partial Microarchitecture passed as input.
    """
    architecture_family = _machine()
    # If a tester is not registered, assume no known target is compatible with the host
    tester = COMPATIBILITY_CHECKS.get(architecture_family, lambda x, y: False)
    return [x for x in TARGETS.values() if tester(info, x)] or [
        generic_microarchitecture(architecture_family)
    ]


def host():
    """Detects the host micro-architecture and returns it."""
    # Retrieve information on the host's cpu
    info = detected_info()

    # Get a list of possible candidates for this micro-architecture
    candidates = compatible_microarchitectures(info)

    # Sorting criteria for candidates
    def sorting_fn(item):
        return len(item.ancestors), len(item.features)

    # Get the best generic micro-architecture
    generic_candidates = [c for c in candidates if c.vendor == "generic"]
    best_generic = max(generic_candidates, key=sorting_fn)

    # Filter the candidates to be descendant of the best generic candidate.
    # This is to avoid that the lack of a niche feature that can be disabled
    # from e.g. BIOS prevents detection of a reasonably performant architecture
    candidates = [c for c in candidates if c > best_generic]

    # If we don't have candidates, return the best generic micro-architecture
    if not candidates:
        return best_generic

    # Reverse sort of the depth for the inheritance tree among only targets we
    # can use. This gets the newest target we satisfy.
    return max(candidates, key=sorting_fn)


def compatibility_check(architecture_family: Union[str, Tuple[str, ...]]):
    """Decorator to register a function as a proper compatibility check.

    A compatibility check function takes a partial Microarchitecture object as a first argument,
    and an arbitrary target Microarchitecture as the second argument. It returns True if the
    target is compatible with first argument, False otherwise.

    Args:
        architecture_family: architecture family for which this test can be used
    """
    # Turn the argument into something iterable
    if isinstance(architecture_family, str):
        architecture_family = (architecture_family,)

    def decorator(func):
        COMPATIBILITY_CHECKS.update({family: func for family in architecture_family})
        return func

    return decorator


@compatibility_check(architecture_family=(PPC64LE, PPC64))
def compatibility_check_for_power(info, target):
    """Compatibility check for PPC64 and PPC64LE architectures."""
    # We can use a target if it descends from our machine type and our
    # generation (9 for POWER9, etc) is at least its generation.
    arch_root = TARGETS[_machine()]
    return (
        target == arch_root or arch_root in target.ancestors
    ) and target.generation <= info.generation


@compatibility_check(architecture_family=X86_64)
def compatibility_check_for_x86_64(info, target):
    """Compatibility check for x86_64 architectures."""
    # We can use a target if it descends from our machine type, is from our
    # vendor, and we have all of its features
    arch_root = TARGETS[X86_64]
    return (
        (target == arch_root or arch_root in target.ancestors)
        and target.vendor in (info.vendor, "generic")
        and target.features.issubset(info.features)
    )


@compatibility_check(architecture_family=AARCH64)
def compatibility_check_for_aarch64(info, target):
    """Compatibility check for AARCH64 architectures."""
    # At the moment, it's not clear how to detect compatibility with
    # a specific version of the architecture
    if target.vendor == "generic" and target.name != AARCH64:
        return False

    arch_root = TARGETS[AARCH64]
    arch_root_and_vendor = arch_root == target.family and target.vendor in (
        info.vendor,
        "generic",
    )

    # On macOS it seems impossible to get all the CPU features
    # with syctl info, but for ARM we can get the exact model
    if platform.system() == "Darwin":
        model = TARGETS[info.name]
        return arch_root_and_vendor and (target == model or target in model.ancestors)

    return arch_root_and_vendor and target.features.issubset(info.features)


@compatibility_check(architecture_family=RISCV64)
def compatibility_check_for_riscv64(info, target):
    """Compatibility check for riscv64 architectures."""
    arch_root = TARGETS[RISCV64]
    return (target == arch_root or arch_root in target.ancestors) and (
        target.name == info.name or target.vendor == "generic"
    )
