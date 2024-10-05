import subprocess
import sys
import os
import argparse

def install_yt_dlp():
    """Install yt-dlp using pip if it's not already installed."""
    try:
        __import__('yt_dlp')
    except ImportError:
        print("yt-dlp not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])

def is_ffmpeg_installed():
    """Check if ffmpeg is installed by trying to run 'ffmpeg -version'."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def install_ffmpeg():
    """Install ffmpeg on Linux using apt-get if it's not already installed."""
    if is_ffmpeg_installed():
        print("ffmpeg is already installed.")
        return

    print("ffmpeg not found. Installing using apt-get...")
    subprocess.check_call(["sudo", "apt-get", "install", "-y", "ffmpeg"])

def download_video(url):
    """Download video using yt-dlp."""
    install_yt_dlp()
    
    yt_dlp = __import__('yt_dlp')

    if not is_ffmpeg_installed():
        install_ffmpeg()

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',  # Download best video and audio separately, merge them
        'outtmpl': '%(title)s.%(ext)s',        # Output file naming pattern
        'merge_output_format': 'mp4',          # Output format after merging
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
        ydl.download([url])

if __name__ == "__main__":

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Download video from a URL using yt-dlp.')
    parser.add_argument('url', help='The URL of the video to download')

    args = parser.parse_args()

    # Download the video from the provided URL
    download_video(args.url)
