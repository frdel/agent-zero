#!/bin/sh

# Detect architecture and set appropriate FALKORDB_BIN_PATH
ARCH=$(uname -m)
case "$ARCH" in
    "x86_64")
        export FALKORDB_BIN_PATH="/FalkorDB/falkor_amd64"
        ;;
    "aarch64")
        export FALKORDB_BIN_PATH="/FalkorDB/falkor_arm64"
        ;;
    *)
        echo "Warning: Unsupported architecture '$ARCH', defaulting to amd64"
        export FALKORDB_BIN_PATH="/FalkorDB/falkor_amd64"
        ;;
esac

echo "Detected architecture: $ARCH"
echo "Using FalkorDB path: $FALKORDB_BIN_PATH"

if [ "${BROWSER:-1}" -eq "1" ]; then
    if [ -d "${FALKORDB_BROWSER_PATH}" ]; then
        cd "${FALKORDB_BROWSER_PATH}" && HOSTNAME="0.0.0.0" node server.js &
    fi
fi

# Create /var/lib/falkordb/data directory if it does not exist
if [ ! -d "${FALKORDB_DATA_PATH}" ]; then
    mkdir "${FALKORDB_DATA_PATH}"
fi

if [ "${TLS:-0}" -eq "1" ]; then
    # shellcheck disable=SC2086
    ${FALKORDB_BIN_PATH}/gen-certs.sh
    # shellcheck disable=SC2086
    exec redis-server ${REDIS_ARGS} --protected-mode no \
        --tls-port 6379 --port 0 \
        --tls-cert-file ${FALKORDB_TLS_PATH}/redis.crt \
        --tls-key-file ${FALKORDB_TLS_PATH}/redis.key \
        --tls-ca-cert-file ${FALKORDB_TLS_PATH}/ca.crt \
        --tls-auth-clients no \
        --dir "${FALKORDB_DATA_PATH}" \
        --loadmodule "${FALKORDB_BIN_PATH}/falkordb.so" ${FALKORDB_ARGS}
else
    # shellcheck disable=SC2086
    exec redis-server ${REDIS_ARGS} --protected-mode no \
        --dir "${FALKORDB_DATA_PATH}" \
        --loadmodule "${FALKORDB_BIN_PATH}/falkordb.so" ${FALKORDB_ARGS}
fi
