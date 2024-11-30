# Sphinx Documentation

This is the source of the [vtk docs](docs.vtk.org) website.

## Build environment

To compile the document locally create a python virtual environment and install the required packages.

For example in Linux / macOS:

```
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Use `make html` in this directory to build the documentation.
Open `_build/html/index.html` in your browser to inspect the result.
