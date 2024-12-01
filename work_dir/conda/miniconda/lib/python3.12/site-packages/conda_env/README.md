# conda-env

Provides the `conda env` interface to Conda environments.

## Installing

`conda env` is included in `conda` itself.

## Usage

All of the usage is documented via the `--help` flag.

```bash
$ conda env --help
usage: conda-env [-h] {create,export,list,remove,update,config} ...

positional arguments:
  {create,export,list,remove,update,config}
    create              Create an environment based on an environment file
    export              Export a given environment
    list                List the Conda environments
    remove              Remove an environment
    update              Update the current environment based on environment file
    config              Configure a conda environment

optional arguments:
  -h, --help            Show this help message and exit.
```


## `environment.yml`

conda-env allows creating environments using the `environment.yml`
specification file. This allows you to specify a name, channels to use when
creating the environment, and the dependencies. For example, to create an
environment named `stats` with numpy and pandas, create an `environment.yml`
file with this as the contents:

```yaml
name: stats
dependencies:
  - numpy
  - pandas
```

Then run this from the command line:

```bash
$ conda env create
Fetching package metadata: ...
Solving package specifications: .Linking packages ...
[      COMPLETE      ] |#################################################| 100%
#
# To activate this environment, use:
# $ conda activate stats
#
# To deactivate this environment, use:
# $ conda deactivate
#
```

Your output might vary a little bit, depending on whether you have the packages
in your local package cache.

You can explicitly provide an environment spec file using `-f` or `--file`
and the name of the file you would like to use.

The default channels can be excluded by adding `nodefaults` to the list of
channels. This is equivalent to passing the `--override-channels` option
to most `conda` commands, and is like `defaults` in the `.condarc`
channel configuration but with the reverse logic.

## Environment file example

```yaml
name: stats
channels:
  - javascript
dependencies:
  - python=3.4   # or 2.7 if you are feeling nostalgic
  - bokeh=0.9.2
  - numpy=1.9.*
  - nodejs=0.10.*
  - flask
  - pip
  - pip:
    - Flask-Testing
```

**Recommendation:** Always create your `environment.yml` file by hand.
