

set -ex



CONDA_SOLVER=libmamba conda create -n test --dry-run scipy
conda create --solver libmamba -n test --dry-run scipy
exit 0
