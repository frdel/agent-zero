

set -ex



pip check
tqdm --help
tqdm -v | rg 4.66.5
pytest -k "not tests_perf"
exit 0
