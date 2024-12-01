# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of pytest fixtures used in conda.gateways tests."""

import json
import os
import socket
from pathlib import Path
from shutil import which

import pytest
from xprocess import ProcessStarter

MINIO_EXE = which("minio")


# rely on tests not requesting this fixture, and pytest not creating this if
# MINIO_EXE was not found
@pytest.fixture()
def minio_s3_server(xprocess, tmp_path):
    """
    Mock a local S3 server using `minio`

    This requires:
    - pytest-xprocess: runs the background process
    - minio: the executable must be in PATH

    Note, the given S3 server will be EMPTY! The test function needs
    to populate it. You can use
    `conda.testing.helpers.populate_s3_server` for that.
    """

    class Minio:
        # The 'name' below will be the name of the S3 bucket containing
        # keys like `noarch/repodata.json`
        # see https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
        name = "minio-s3-server"
        port = 9000

        def __init__(self):
            (Path(tmp_path) / self.name).mkdir()

        @property
        def server_url(self):
            return f"{self.endpoint}/{self.name}"

        @property
        def endpoint(self):
            return f"http://localhost:{self.port}"

        def populate_bucket(self, endpoint, bucket_name, channel_dir):
            """Prepare the s3 connection for our minio instance"""
            from boto3.session import Session
            from botocore.client import Config

            # Make the minio bucket public first
            # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-example-bucket-policies.html#set-a-bucket-policy
            session = Session()
            client = session.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id="minioadmin",
                aws_secret_access_key="minioadmin",
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            bucket_policy = json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AddPerm",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": f"arn:aws:s3:::{bucket_name}/*",
                        }
                    ],
                }
            )
            client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)

            # Minio has to start with an empty directory; once available,
            # we can import all channel files by "uploading" them
            for current, _, files in os.walk(channel_dir):
                for f in files:
                    path = Path(current, f)
                    key = path.relative_to(channel_dir)
                    client.upload_file(
                        str(path),
                        bucket_name,
                        str(key).replace("\\", "/"),  # MinIO expects Unix paths
                        ExtraArgs={"ACL": "public-read"},
                    )

    print("Starting mock_s3_server")
    minio = Minio()

    class Starter(ProcessStarter):
        pattern = "MinIO Object Storage Server"
        terminate_on_interrupt = True
        timeout = 10
        args = [
            MINIO_EXE,
            "server",
            f"--address=:{minio.port}",
            tmp_path,
        ]

        def startup_check(self, port=minio.port):
            s = socket.socket()
            address = "localhost"
            error = False
            try:
                s.connect((address, port))
            except Exception as e:
                print(
                    "something's wrong with %s:%d. Exception is %s" % (address, port, e)
                )
                error = True
            finally:
                s.close()

            return not error

    # ensure process is running and return its logfile
    pid, logfile = xprocess.ensure(minio.name, Starter)
    print(f"Server (PID: {pid}) log file can be found here: {logfile}")
    yield minio
    xprocess.getinfo(minio.name).terminate()
