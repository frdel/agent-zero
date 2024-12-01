#!/usr/bin/env bash
# Run the tests for CA-Certificates Verify if the ca certificates exists for windows platform.

set -ex
exists() {
	FULL_PATH="${PREFIX}/${1}"
	if [ -f "${FULL_PATH}" ]; then
		echo "Found ${1}"
	else
		echo "Could not find ${FULL_PATH}"
		exit 1
	fi
}
for i in ssl/{cacert,cert}.pem ; do
	exists $i
done
user_cert() {
	exit_status=$1
	if [ "$exit_status" -eq 0 ]; then
		echo "Able to use ca certificate"
	else
		echo "Failed to use ca cert files"
		exit 1
	fi
}
curl --cacert "${PREFIX}/ssl/cacert.pem" https://www.google.com
user_cert $?
