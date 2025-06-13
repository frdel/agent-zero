import sys
import yt_dlp # type: ignore

if len(sys.argv) != 2:
    print("Usage: python3 download_video.py <url>")
    sys.exit(1)

url = sys.argv[1]

ydl_opts = {}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
