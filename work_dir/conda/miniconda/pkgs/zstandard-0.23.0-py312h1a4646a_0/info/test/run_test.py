#  tests for zstandard-0.23.0-py312h1a4646a_0 (this is a generated file);
print('===== testing package: zstandard-0.23.0-py312h1a4646a_0 =====');
print('running run_test.py');
#  --- run_test.py (begin) ---
import zstandard as zstd

data = b'foo'

compress = zstd.ZstdCompressor(write_checksum=True, write_content_size=True).compress
decompress = zstd.ZstdDecompressor().decompress

assert decompress(compress(data)) == data
#  --- run_test.py (end) ---

print('===== zstandard-0.23.0-py312h1a4646a_0 OK =====');
print("import: 'zstandard'")
import zstandard

