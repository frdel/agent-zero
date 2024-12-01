"""
Simple test for evaluating zstandard binding memory usage.
"""

import io
import sys

import zstandard

if __name__ == "__main__":
    times = 100
    if len(sys.argv) == 3:
        times = int(sys.argv[2])

    for i in range(times):
        compressor = zstandard.ZstdCompressor(level=int(sys.argv[1]))
        writer = compressor.stream_writer(io.BytesIO())
        writer.write(b"hello")
        writer.close()
