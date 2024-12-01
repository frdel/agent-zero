# https://martinopilia.com/posts/2018/09/15/building-python-extension.html
cmake_minimum_required(VERSION 3.10)
enable_language(C)
project(mymath)

option(PY_VER, "Python version to use")

find_package(PythonInterp ${PY_VER} REQUIRED)
#             PATHS $ENV{CONDA_PREFIX})
# This goes after, since it uses PythonInterp as hint
find_package(PythonLibs ${PY_VER} REQUIRED)
