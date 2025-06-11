# import sys
# from types import ModuleType, SimpleNamespace

# import numpy  # real numpy

# # for python 3.12 on arm, faiss needs a fake cpuinfo module


# """ This disgusting hack was brought to you by:
# https://github.com/facebookresearch/faiss/issues/3936
# """

# faiss_monkey_patch.py  – import this before faiss -----------------
import sys, types, numpy as np
from types import SimpleNamespace

# fake numpy.distutils and numpy.distutils.cpuinfo packages
dist = types.ModuleType("numpy.distutils")
cpuinfo = types.ModuleType("numpy.distutils.cpuinfo")

# cpu attribute that looks like the real one
cpuinfo.cpu = SimpleNamespace( # type: ignore
    # FAISS only does   .info[0].get('Features', '')
    info=[{}]
)

# register in sys.modules
dist.cpuinfo = cpuinfo # type: ignore
sys.modules["numpy.distutils"] = dist
sys.modules["numpy.distutils.cpuinfo"] = cpuinfo

# crucial: expose it as an *attribute* of the already-imported numpy package
np.distutils = dist # type: ignore
# -------------------------------------------------------------------

import faiss