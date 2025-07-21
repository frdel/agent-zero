# api/synthesize.py

from python.helpers.api import ApiHandler, Request, Response

from python.helpers import runtime, settings, kokoro_tts

class Synthesize(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        text = input.get("text", "")
        ctxid = input.get("ctxid", "")
        
        context = self.get_context(ctxid)
        if not await kokoro_tts.is_downloaded():
            context.log.log(type="info", content="Kokoro TTS model is currently being initialized, please wait...")

        try:
            # # Clean and chunk text for long responses
            # cleaned_text = self._clean_text(text)
            # chunks = self._chunk_text(cleaned_text)
            
            # if len(chunks) == 1:
            #     # Single chunk - return as before
            #     audio = await kokoro_tts.synthesize_sentences(chunks)
            #     return {"audio": audio, "success": True}
            # else:
            #     # Multiple chunks - return as sequence
            #     audio_parts = []
            #     for chunk in chunks:
            #         chunk_audio = await kokoro_tts.synthesize_sentences([chunk])
            #         audio_parts.append(chunk_audio)
            #     return {"audio_parts": audio_parts, "success": True}

            # audio is chunked on the frontend for better flow
            audio = await kokoro_tts.synthesize_sentences([text])
            return {"audio": audio, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    # def _clean_text(self, text: str) -> str:
    #     """Clean text by removing markdown, tables, code blocks, and other formatting"""
    #     # Remove code blocks
    #     text = re.sub(r'```[\s\S]*?```', '', text)
    #     text = re.sub(r'`[^`]*`', '', text)
        
    #     # Remove markdown links
    #     text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
    #     # Remove markdown formatting
    #     text = re.sub(r'[*_#]+', '', text)
        
    #     # Remove tables (basic cleanup)
    #     text = re.sub(r'\|[^\n]*\|', '', text)
        
    #     # Remove extra whitespace and newlines
    #     text = re.sub(r'\n+', ' ', text)
    #     text = re.sub(r'\s+', ' ', text)
        
    #     # Remove URLs
    #     text = re.sub(r'https?://[^\s]+', '', text)
        
    #     # Remove email addresses
    #     text = re.sub(r'\S+@\S+', '', text)
        
    #     return text.strip()
    
    # def _chunk_text(self, text: str) -> list[str]:
    #     """Split text into manageable chunks for TTS"""
    #     # If text is short enough, return as single chunk
    #     if len(text) <= 300:
    #         return [text]
        
    #     # Split into sentences first
    #     sentences = re.split(r'(?<=[.!?])\s+', text)
        
    #     chunks = []
    #     current_chunk = ""
        
    #     for sentence in sentences:
    #         sentence = sentence.strip()
    #         if not sentence:
    #             continue
                
    #         # If adding this sentence would make chunk too long, start new chunk
    #         if current_chunk and len(current_chunk + " " + sentence) > 300:
    #             chunks.append(current_chunk.strip())
    #             current_chunk = sentence
    #         else:
    #             current_chunk += (" " if current_chunk else "") + sentence
        
    #     # Add the last chunk if it has content
    #     if current_chunk.strip():
    #         chunks.append(current_chunk.strip())
        
    #     return chunks if chunks else [text]