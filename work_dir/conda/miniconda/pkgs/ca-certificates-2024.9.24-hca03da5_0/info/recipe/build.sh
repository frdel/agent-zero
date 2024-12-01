#!/bin/bash

# Create the directory to hold the certificates.
mkdir -p "${PREFIX}/ssl"

# Move the certificates.
mv cacert.pem ${PREFIX}/ssl/cacert.pem
ln -fs "${PREFIX}/ssl/cacert.pem" "${PREFIX}/ssl/cert.pem"
