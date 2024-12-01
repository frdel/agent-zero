#!/bin/bash

set -e

echo "Environment tester"
echo "------------------------"
T_PREFIX=$(cd $1 && pwd); shift
echo "prefix ... $T_PREFIX"

echo -n "python ... "
T_PYTHON_WIN=$T_PREFIX/python.exe
T_PYTHON_UNX=$T_PREFIX/bin/python
if [ -x $T_PYTHON_WIN ]; then
  T_PYTHON=$T_PYTHON_WIN
elif [ -x $T_PYTHON_UNX ]; then
  T_PYTHON=$T_PYTHON_UNX
fi
if [ -z "$T_PYTHON" ]; then
  echo "MISSING"
  exit -1
fi
echo $T_PYTHON

success=yes

echo
export ANACONDA_ANON_USAGE_DEBUG=1
cmd="$T_PYTHON -m conda list"
echo "\$ $cmd"
echo "------------------------"
pkgs=$($cmd 2>&1)
echo "$pkgs" | grep -vE '^ *$'
echo "------------------------"

echo
cmd="$T_PYTHON -m conda info"
echo "\$ $cmd"
echo "------------------------"
cinfo=$($cmd 2>&1)
echo "$cinfo" | grep -vE '^ *$'
echo "------------------------"

echo
export CONDA_ANACONDA_ANON_USAGE=no
echo "\$ CONDA_ANACONDA_ANON_USAGE=no $cmd"
echo "------------------------"
cinfo_d=$($cmd 2>&1)
echo "$cinfo_d" | grep -vE '^ *$'
echo "------------------------"

echo
echo -n "user agent (enabled) ... "
user_agent=$(echo "$cinfo" | sed -nE 's@.*user-agent : (.*)@\1@p')
if echo "$user_agent" | grep -qE " c/.* s/.* e/"; then
  echo "yes: $user_agent"
else
  echo "NO: $user_agent"
  success=no
fi

echo -n "user agent (disabled) ... "
user_agent=$(echo "$cinfo_d" | sed -nE 's@.*user-agent : (.*)@\1@p')
if echo "$user_agent" | grep -qE " (c|s|e)/"; then
  echo "NO: $user_agent"
  success=no
else
  echo "yes: $user_agent"
fi

if [ "$success" = yes ]; then
  echo "success!"
  exit 0
else
  echo "one or more errors detected"
  exit -1
fi
