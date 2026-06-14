"""
Voiceover Generator — Microsoft Edge TTS (miễn phí, giọng Việt tự nhiên)
"""
import asyncio
import os

VOICES = {
    "nu_mien_bac":  "vi-VN-HoaiMyNeural",    # Giọng nữ miền Bắc (tự nhiên nhất)
    "nam_mien_bac": "vi-VN-NamMinhNeural",   # Giọng nam miền Bắc
}


async def _create_voiceover(text: str, output_path: str, voice_key: str = "nu_mien_bac",
                             rate: str = "+15%", volume: str = "+5%"):
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts chưa cài. Chạy: pip install edge-tts")

    voice = VOICES.get(voice_key, VOICES["nu_mien_bac"])
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    await communicate.save(output_path)
    return output_path


def generate_voiceover(text: str, output_path: str, voice_key: str = "nu_mien_bac") -> str:
    """Tạo file MP3 voiceover từ text (sync wrapper)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    asyncio.run(_create_voiceover(text, output_path, voice_key))
    return output_path


async def generate_voiceover_async(text: str, output_path: str, voice_key: str = "nu_mien_bac") -> str:
    """Async version."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    await _create_voiceover(text, output_path, voice_key)
    return output_path
