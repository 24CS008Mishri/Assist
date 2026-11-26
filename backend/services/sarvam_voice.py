"""Sarvam speech for the opt-in Tavus audio passthrough path."""
import base64
from functools import lru_cache
import io
import os
import wave

import httpx

LANGUAGES = {f"{code}-IN" for code in ("en", "hi", "gu", "bn", "ta", "te", "kn", "ml", "mr", "pa", "od")}


def echo_pal():
    return os.getenv("TAVUS_SARVAM_PAL_ID", "").strip() if os.getenv("SARVAM_API_KEY") else ""


@lru_cache(maxsize=2)
def _client(key):
    return httpx.Client(base_url="https://api.sarvam.ai", headers={"api-subscription-key": key}, timeout=6)


def transcribe(audio, content_type):
    response = _client(os.environ["SARVAM_API_KEY"]).post(
        "/speech-to-text",
        files={"file": ("turn", audio, content_type)},
        data={"model": "saaras:v4", "mode": "codemix", "language_code": "unknown"},
    )
    response.raise_for_status()
    result = response.json()
    return (result.get("transcript") or "").strip()[:2000], result.get("language_code")


@lru_cache(maxsize=96)
def short_audio(text, language):
    # Cache only fixed greetings and status lines, never a private reply.
    return synthesize(text, language)


def synthesize(text, language):
    response = _client(os.environ["SARVAM_API_KEY"]).post("/text-to-speech", json={
        "text": text, "target_language_code": language, "model": "bulbul:v3",
        "speaker": "kavya", "speech_sample_rate": 24000, "pace": 1.0,
    })
    response.raise_for_status()
    wav = base64.b64decode(response.json()["audios"][0], validate=True)
    with wave.open(io.BytesIO(wav)) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
            raise ValueError("Unexpected Sarvam audio format")
        pcm = audio.readframes(audio.getnframes())
    return base64.b64encode(pcm).decode("ascii")
