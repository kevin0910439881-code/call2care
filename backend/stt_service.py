import os
from groq import Groq
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Groq client
api_key = os.getenv("GROQ_API_KEY")
if api_key and api_key != "your_groq_api_key_here":
    client = Groq(api_key=api_key)
else:
    client = None

def transcribe_audio_bytes(filename: str, audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes using Groq's whisper-large-v3 model.
    """
    if not client:
        return "STT Error: Groq API key is not configured."

    try:
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3",
            language="zh",
            prompt="這是一段繁體中文的台灣口音醫學對話，請一律用繁體中文輸出。",
            response_format="text"
        )
        
        if isinstance(transcription, str):
            result_text = transcription.strip()
        elif hasattr(transcription, 'text'):
            result_text = transcription.text.strip()
        else:
            result_text = str(transcription).strip()
            
        # Filter out common Whisper hallucinations on silence/noise
        hallucinations = [
            "明镜与点点栏目",
            "请不吝点赞",
            "订阅",
            "转发",
            "Amara.org",
            "谢谢观看",
            "感谢观看"
        ]
        
        for h in hallucinations:
            if h in result_text:
                logger.info(f"Filtered hallucination: {result_text}")
                return ""
                
        logger.info(f"STT Transcript: {result_text}")
        return result_text
            
    except Exception as e:
        logger.error(f"STT Service Error: {e}")
        return f"STT Error: {str(e)}"
