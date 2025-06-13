#!/bin/bash

echo "====================SEARXNG2 START===================="


# clone SearXNG repo
git clone "https://github.com/searxng/searxng" \
                   "/usr/local/searxng/searxng-src"

echo "====================SEARXNG2 VENV===================="

# create virtualenv:
python3.12 -m venv "/usr/local/searxng/searx-pyenv"

# make it default
echo ". /usr/local/searxng/searx-pyenv/bin/activate" \
                   >>  "/usr/local/searxng/.profile"

# activate venv
source "/usr/local/searxng/searx-pyenv/bin/activate"

echo "====================SEARXNG2 INST===================="

# update pip's boilerplate
pip install -U pip
pip install -U setuptools
pip install -U wheel
pip install -U pyyaml

# jump to SearXNG's working tree and install SearXNG into virtualenv
cd "/usr/local/searxng/searxng-src"
pip install --use-pep517 --no-build-isolation -e .

# cleanup cache
pip cache purge

echo "====================SEARXNG2 END===================="