# -*- coding: utf-8 -*-
#
#     Copyright (c) 2024 Anders Høst
#

from __future__ import print_function

import struct
import cpuid


def cpu_vendor(cpu):
    _, b, c, d = cpu(0)
    return struct.pack("III", b, d, c).decode("utf-8")


def cpu_name(cpu):
    name = "".join((struct.pack("IIII", *cpu(0x80000000 + i)).decode("utf-8")
                    for i in range(2, 5)))

    return name.split('\x00', 1)[0]


def is_set(cpu, leaf, subleaf, reg_idx, bit):
    """
    @param {leaf} %eax
    @param {sublead} %ecx, 0 in most cases
    @param {reg_idx} idx of [%eax, %ebx, %ecx, %edx], 0-based
    @param {bit} bit of reg selected by {reg_idx}, 0-based
    """

    regs = cpu(leaf, subleaf)

    if (1 << bit) & regs[reg_idx]:
        return "Yes"
    else:
        return "--"


if __name__ == "__main__":
    cpu = cpuid.CPUID()

    print("Vendor ID : %s" % cpu_vendor(cpu))
    print("CPU name  : %s" % cpu_name(cpu))
    print()
    print("Vector instructions supported:")
    print("SSE       : %s" % is_set(cpu, 1, 0, 3, 25))
    print("SSE2      : %s" % is_set(cpu, 1, 0, 3, 26))
    print("SSE3      : %s" % is_set(cpu, 1, 0, 2, 0))
    print("SSSE3     : %s" % is_set(cpu, 1, 0, 2, 9))
    print("SSE4.1    : %s" % is_set(cpu, 1, 0, 2, 19))
    print("SSE4.2    : %s" % is_set(cpu, 1, 0, 2, 20))
    print("SSE4a     : %s" % is_set(cpu, 0x80000001, 0, 2, 6))
    print("AVX       : %s" % is_set(cpu, 1, 0, 2, 28))
    print("AVX2      : %s" % is_set(cpu, 7, 0, 1, 5))
    print("BMI1      : %s" % is_set(cpu, 7, 0, 1, 3))
    print("BMI2      : %s" % is_set(cpu, 7, 0, 1, 8))
    # Intel RDT CMT/MBM
    print("L3 Monitoring : %s" % is_set(cpu, 0xf, 0, 3, 1))
    print("L3 Occupancy  : %s" % is_set(cpu, 0xf, 1, 3, 0))
    print("L3 Total BW   : %s" % is_set(cpu, 0xf, 1, 3, 1))
    print("L3 Local BW   : %s" % is_set(cpu, 0xf, 1, 3, 2))
