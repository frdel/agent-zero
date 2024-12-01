import io
import pathlib
import struct

import pytest

from packaging._elffile import EIClass, EIData, ELFFile, ELFInvalid, EMachine

DIR_MANYLINUX = pathlib.Path(__file__, "..", "manylinux").resolve()
DIR_MUSLLINUX = pathlib.Path(__file__, "..", "musllinux").resolve()
BIN_MUSL_X86_64 = DIR_MUSLLINUX.joinpath("musl-x86_64").read_bytes()


@pytest.mark.parametrize(
    "name, capacity, encoding, machine",
    [
        ("x86_64-x32", EIClass.C32, EIData.Lsb, EMachine.X8664),
        ("x86_64-i386", EIClass.C32, EIData.Lsb, EMachine.I386),
        ("x86_64-amd64", EIClass.C64, EIData.Lsb, EMachine.X8664),
        ("armv7l-armel", EIClass.C32, EIData.Lsb, EMachine.Arm),
        ("armv7l-armhf", EIClass.C32, EIData.Lsb, EMachine.Arm),
        ("s390x-s390x", EIClass.C64, EIData.Msb, EMachine.S390),
    ],
)
def test_elffile_glibc(name, capacity, encoding, machine):
    path = DIR_MANYLINUX.joinpath(f"hello-world-{name}")
    with path.open("rb") as f:
        ef = ELFFile(f)
        assert ef.capacity == capacity
        assert ef.encoding == encoding
        assert ef.machine == machine
        assert ef.flags is not None


@pytest.mark.parametrize(
    "name, capacity, encoding, machine, interpreter",
    [
        (
            "aarch64",
            EIClass.C64,
            EIData.Lsb,
            EMachine.AArc64,
            "aarch64",
        ),
        ("i386", EIClass.C32, EIData.Lsb, EMachine.I386, "i386"),
        ("x86_64", EIClass.C64, EIData.Lsb, EMachine.X8664, "x86_64"),
    ],
)
def test_elffile_musl(name, capacity, encoding, machine, interpreter):
    path = DIR_MUSLLINUX.joinpath(f"musl-{name}")
    with path.open("rb") as f:
        ef = ELFFile(f)
        assert ef.capacity == capacity
        assert ef.encoding == encoding
        assert ef.machine == machine
        assert ef.interpreter == f"/lib/ld-musl-{interpreter}.so.1"


@pytest.mark.parametrize(
    "data",
    [
        # Too short for magic.
        b"\0",
        # Enough for magic, but not ELF.
        b"#!/bin/bash" + b"\0" * 16,
        # ELF, but unknown byte declaration.
        b"\x7fELF\3" + b"\0" * 16,
    ],
    ids=["no-magic", "wrong-magic", "unknown-format"],
)
def test_elffile_bad_ident(data):
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_elffile_no_section():
    """Enough for magic, but not the section definitions."""
    data = BIN_MUSL_X86_64[:25]
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_elffile_invalid_section():
    """Enough for section definitions, but not the actual sections."""
    data = BIN_MUSL_X86_64[:58]
    assert ELFFile(io.BytesIO(data)).interpreter is None


def test_elffle_no_interpreter_section():
    ef = ELFFile(io.BytesIO(BIN_MUSL_X86_64))

    # Change all sections to *not* PT_INTERP.
    data = BIN_MUSL_X86_64
    for i in range(ef._e_phnum + 1):
        sb = ef._e_phoff + ef._e_phentsize * i
        se = sb + ef._e_phentsize
        section = struct.unpack(ef._p_fmt, data[sb:se])
        data = data[:sb] + struct.pack(ef._p_fmt, 0, *section[1:]) + data[se:]

    assert ELFFile(io.BytesIO(data)).interpreter is None
