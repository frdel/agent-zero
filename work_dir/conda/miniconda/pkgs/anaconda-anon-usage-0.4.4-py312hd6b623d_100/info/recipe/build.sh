"${PREFIX}/bin/python" -m pip install --no-deps --no-build-isolation --ignore-installed -vv .
if [ "$NEED_SCRIPTS" == no ]; then
    rm ${SP_DIR}/anaconda_anon_usage/install.py
    exit 0
fi
rm ${SP_DIR}/anaconda_anon_usage/plugin.py
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "scripts/activate.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
mkdir -p "${PREFIX}/bin"
cp "scripts/post-link.sh" "${PREFIX}/bin/.${PKG_NAME}-post-link.sh"
cp "scripts/pre-unlink.sh" "${PREFIX}/bin/.${PKG_NAME}-pre-unlink.sh"
