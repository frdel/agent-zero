import os

try:
    from libmambapy.bindings import *  # noqa: F401,F403
except ImportError as e:
    if not os.environ.get("CONDA_BUILD_CROSS_COMPILATION"):
        raise e
    else:
        print("libmambapy import error ignored due to cross compilation")
