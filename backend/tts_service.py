import os
import asyncio
import edge_tts
import logging

logger = logging.getLogger(__name__)

VOICE = "zh-TW-HsiaoChenNeural"

async def generate_tts_async(text: str, output_path: str = "response.mp3"):
    """
    Generates TTS audio using edge-tts asynchronously.
    """
    try:
        logger.info(f"Generating TTS for text (len {len(text)})...")
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_path)
        logger.info(f"TTS audio saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}")
        return None


