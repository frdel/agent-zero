#!/bin/bash

set -e

version=$1; shift
vflag="==$version"

SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)
source $CONDA_PREFIX/*/activate
# Needed to convert windows path to unix
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)

cat >construct.yaml <<EOD
name: AIDTest
version: 1.0
installer_type: all
channels:
  - local
  - defaults
specs:
  - conda${vflag:-}
  - anaconda-anon-usage
EOD

echo "-----"
cat construct.yaml
echo "-----"

constructor .

if [ -f AIDTest*.sh ]; then
  echo ".sh installer created"
elif [ -f AIDTest*.exe ]; then
  echo ".exe installer created"
else
  echo "No testable installer created"
  exit -1
fi
