#!/bin/sh

# Generate some test certificates which are used by the regression test suite:
#
#   tls/ca.{crt,key}          Self signed CA certificate.
#   tls/redis.{crt,key}       A certificate with no key usage/policy restrictions.
#   tls/client.{crt,key}      A certificate restricted for SSL client usage.
#   tls/server.{crt,key}      A certificate restricted for SSL server usage.
#   tls/redis.dh              DH Params file.

generate_cert() {
    local name=$1
    local cn="$2"
    local opts="$3"

    local keyfile=${FALKORDB_TLS_PATH}/${name}.key
    local certfile=${FALKORDB_TLS_PATH}/${name}.crt

    [ -f $keyfile ] || openssl genrsa -out $keyfile 2048
    openssl req \
        -new -sha256 \
        -subj "/O=FalkorDB/CN=$cn" \
        -key $keyfile | \
        openssl x509 \
            -req -sha256 \
            -CA ${FALKORDB_TLS_PATH}/ca.crt \
            -CAkey ${FALKORDB_TLS_PATH}/ca.key \
            -CAserial ${FALKORDB_TLS_PATH}/ca.txt \
            -CAcreateserial \
            -days 365 \
            $opts \
            -out $certfile
}

mkdir -p ${FALKORDB_TLS_PATH}
[ -f "${FALKORDB_TLS_PATH}/ca.key" ] || openssl genrsa -out ${FALKORDB_TLS_PATH}/ca.key 4096
[ -f "${FALKORDB_TLS_PATH}/ca.crt" ] || openssl req \
    -x509 -new -nodes -sha256 \
    -key ${FALKORDB_TLS_PATH}/ca.key \
    -days 3650 \
    -subj '/O=Redis Test/CN=Certificate Authority' \
    -out ${FALKORDB_TLS_PATH}/ca.crt

[ -f "${FALKORDB_TLS_PATH}/openssl.cnf" ] || cat > ${FALKORDB_TLS_PATH}/openssl.cnf <<_END_
[ server_cert ]
keyUsage = digitalSignature, keyEncipherment
nsCertType = server

[ client_cert ]
keyUsage = digitalSignature, keyEncipherment
nsCertType = client
_END_

generate_cert server "Server-only" "-extfile ${FALKORDB_TLS_PATH}/openssl.cnf -extensions server_cert"
generate_cert client "Client-only" "-extfile ${FALKORDB_TLS_PATH}/openssl.cnf -extensions client_cert"
generate_cert redis "Generic-cert"

[ -f ${FALKORDB_TLS_PATH}/redis.dh ] || openssl dhparam -out ${FALKORDB_TLS_PATH}/redis.dh 2048
