

set -ex



export ANACONDA_ANON_USAGE_DEBUG=1
export PYTHONUNBUFFERED=1
conda create -n testchild1 --yes
conda create -n testchild2 --yes
conda info
conda info --envs
pytest -v tests/unit
python tests/integration/test_config.py
exit 0
