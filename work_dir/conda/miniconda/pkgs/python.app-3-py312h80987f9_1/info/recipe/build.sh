#!/bin/bash

# FIXME:
# pythonw this should really be the compiled program Mac/Tools/pythonw.c
# note that PYTHONEXECUTABLE is used to fix argv[0] (see Modules/main.c)

APP_DIR=$PREFIX/pythonapp
mkdir $APP_DIR
cp -r $RECIPE_DIR/Contents $APP_DIR
MACOS_DIR=$APP_DIR/Contents/MacOS
mkdir -p $MACOS_DIR

# We used to copy over python, which could cause the Python binaries in
# the `python` and `python.app` packages to diverge, leading to issues
# (see https://github.com/conda-forge/python.app-feedstock/issues/8)
# Leave this line here for historical reasons.
# cp $PREFIX/bin/python $MACOS_DIR

# New approach: create a symlink, so the python binary used in `python.app`
# (and `pythonw`) will always be the one installed via the `python` package.
ln -s ../../../bin/python $MACOS_DIR/python

PYAPP=$PREFIX/bin/python.app
cat <<EOF >$PYAPP
#!/bin/bash
export PYTHONEXECUTABLE=$PREFIX/bin/python
$PREFIX/python.app/Contents/MacOS/python "\$@"
EOF
chmod +x $PYAPP

BIN=$PREFIX/bin
cd $BIN
cp python.app pythonw

POST_LINK=$BIN/.python.app-post-link.sh
PRE_UNLINK=$BIN/.python.app-pre-unlink.sh
cp $RECIPE_DIR/post-link.sh $POST_LINK
cp $RECIPE_DIR/pre-unlink.sh $PRE_UNLINK
chmod +x $POST_LINK $PRE_UNLINK
