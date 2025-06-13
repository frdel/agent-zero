import sys
from youtube_transcript_api._api import YouTubeTranscriptApi

def get_youtube_transcript(video_url):
    try:
        # Extract video ID from URL
        video_id = video_url.split('v=')[1].split('&')[0]
        
        # Get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine all transcript entries into a single string
        full_transcript = ''
        for entry in transcript:
            full_transcript += entry['text'] + '\n'
            
        return full_transcript
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        video_url = sys.argv[1]
        transcript = get_youtube_transcript(video_url)
        print(transcript)
    else:
        print("Please provide a YouTube video URL as an argument.") 