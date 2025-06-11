import sys
from types import ModuleType, SimpleNamespace

import numpy  # real numpy

# for python 3.12 on arm, faiss needs a fake cpuinfo module


""" This disgusting hack was brought to you by:
https://github.com/facebookresearch/faiss/issues/3936
"""

def hack_faiss_for_python_3_12() -> None:
    # Create a fake 'cpuinfo' module
    fake_cpuinfo_module = ModuleType("numpy.distutils.cpuinfo")
    fake_cpu_module = SimpleNamespace()
    fake_cpu_module.info = [{"Features": "asimd fp"}]  # No 'sve'
    setattr(fake_cpuinfo_module, "cpu", fake_cpu_module)

    # Create a fake 'distutils' module and assign the cpuinfo module
    fake_distutils_module = ModuleType("numpy.distutils")
    setattr(fake_distutils_module, "cpuinfo", fake_cpuinfo_module)

    # Inject the fake modules into sys.modules
    sys.modules["numpy.distutils"] = fake_distutils_module
    sys.modules["numpy.distutils.cpuinfo"] = fake_cpuinfo_module

hack_faiss_for_python_3_12()