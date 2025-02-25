import json
import os
from ..helpers.tool import Tool, Response
from ..helpers.errors import handle_error

class QuranAudioTool(Tool):
    AUDIO_METADATA_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data/cdn_surah_audio.json")
    AUDIO_BASE_URL = "https://cdn.islamic.network/quran/audio-surah"

    async def find_reciter(self, reciter_name):
        with open(self.AUDIO_METADATA_JSON_PATH, "r") as f:
            editions = json.load(f)

        if not reciter_name:
            return editions[0]

        # Convert search name to lowercase for case-insensitive matching
        search_name = reciter_name.lower()
        
        def calculate_match_score(edition):
            eng_name = edition['englishName'].lower()
            ar_name = edition['name'].lower()
            
            # Calculate character-by-character match scores
            eng_score = sum(1 for c in search_name if c in eng_name)
            ar_score = sum(1 for c in search_name if c in ar_name)
            
            # Exact match bonus
            if search_name == eng_name or search_name == ar_name:
                return float('inf')  # Prioritize exact matches
            
            # Substring match bonus
            if search_name in eng_name or search_name in ar_name:
                return max(eng_score, ar_score) * 2
                
            return max(eng_score, ar_score)

        # Sort editions by match score
        matched_editions = [(edition, calculate_match_score(edition)) for edition in editions]
        matched_editions.sort(key=lambda x: x[1], reverse=True)
        
        # Return the best match
        return matched_editions[0][0]

    async def execute(self, surah_number=None, reciter_name=None, **kwargs):
        if not surah_number or not str(surah_number).isdigit():
                return Response(
                    message="Please provide a valid surah number (1-114)",
                    break_loop=False
                )

        surah_number = int(surah_number)
        if not 1 <= surah_number <= 114:
            return Response(
                message="Surah number must be between 1 and 114",
                break_loop=False
            )
        
        edition_info = await self.find_reciter(reciter_name)
        
        edition = edition_info['identifier']
        
        try:
            audio_url = f"{self.AUDIO_BASE_URL}/{edition_info['bitrate']}/{edition}/{surah_number}.mp3"
            result = {
                    "tool_name": "response",
                    "tool_args": {
                        "text": audio_url,
                        "type": "audio",
                        "data": {
                            "url": audio_url,
                            "metadata": {
                                "title": f"Surah {surah_number}",
                                "format": "mp3",
                                "bitrate": edition_info["bitrate"],
                                "language": edition_info["language"],
                                "reciter": edition_info["englishName"]
                            }
                        }
                    }
                }
            return Response(message=json.dumps(result), break_loop=False)

        except Exception as e:
            handle_error(e)
            return Response(
                message=f"Error fetching audio: {str(e)}",
                break_loop=False
            )

    def get_log_object(self, **kwargs):
        return self.agent.context.log.log(
            type="tool",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=kwargs.get('args', {})
        )

    async def after_execution(self, response, **kwargs):
        tool_result = json.dumps(response.message) if isinstance(response.message, dict) else str(response.message)
        await self.agent.hist_add_tool_result(self.name, tool_result)