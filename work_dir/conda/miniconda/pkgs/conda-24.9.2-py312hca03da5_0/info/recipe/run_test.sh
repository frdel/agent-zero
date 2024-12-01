#!/usr/bin/env bash

# clear conda stuff from parent process
unset CONDA_SHLVL
unset _CE_CONDA
unset _CE_M
unset CONDA_EXE

# load shell interface
eval "$(python -m conda shell.bash hook)"

# display conda details
conda info --all

# create, activate, and deactivate a conda environment
conda create --yes --prefix "./built-conda-test-env" "patch" || exit 1

conda activate "./built-conda-test-env"
echo "CONDA_PREFIX=${CONDA_PREFIX}"

[[ "${CONDA_PREFIX}" == "${PWD}/built-conda-test-env" ]] || exit 1
${CONDA_PREFIX}/bin/patch --version || exit 1

conda deactivate
