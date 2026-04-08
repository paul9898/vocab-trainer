from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv

try:
    from backend.db import ROOT_DIR
except ImportError:  # pragma: no cover - supports direct script execution
    from db import ROOT_DIR


load_dotenv(ROOT_DIR / ".env")

GOOGLE_TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_TTS_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
TTS_CACHE_DIR = ROOT_DIR / "backend" / "data" / "tts_cache"


class TTSConfigurationError(RuntimeError):
    pass


class TTSProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class TTSSettings:
    provider: str = "browser"
    language_code: str = "th-TH"
    voice_name: str = "th-TH-Standard-A"
    audio_encoding: str = "MP3"
    word_rate: float = 0.82
    sentence_rate: float = 0.9


def load_tts_settings() -> TTSSettings:
    provider = os.getenv("TTS_PROVIDER", "browser").strip().lower() or "browser"
    return TTSSettings(
        provider=provider,
        language_code=os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "th-TH").strip() or "th-TH",
        voice_name=os.getenv("GOOGLE_TTS_VOICE_NAME", "th-TH-Standard-A").strip() or "th-TH-Standard-A",
        audio_encoding=os.getenv("GOOGLE_TTS_AUDIO_ENCODING", "MP3").strip().upper() or "MP3",
        word_rate=float(os.getenv("GOOGLE_TTS_WORD_RATE", "0.82")),
        sentence_rate=float(os.getenv("GOOGLE_TTS_SENTENCE_RATE", "0.9")),
    )


def build_google_synthesis_payload(text: str, mode: str, settings: TTSSettings) -> dict[str, object]:
    speaking_rate = settings.word_rate if mode == "word" else settings.sentence_rate
    return {
        "input": {"text": text},
        "voice": {
            "languageCode": settings.language_code,
            "name": settings.voice_name,
        },
        "audioConfig": {
            "audioEncoding": settings.audio_encoding,
            "speakingRate": speaking_rate,
        },
    }


def _cache_extension(audio_encoding: str) -> str:
    if audio_encoding.upper() == "MP3":
        return "mp3"
    return "bin"


def build_tts_cache_key(text: str, mode: str, settings: TTSSettings) -> str:
    payload = {
        "provider": settings.provider,
        "language_code": settings.language_code,
        "voice_name": settings.voice_name,
        "audio_encoding": settings.audio_encoding,
        "word_rate": settings.word_rate,
        "sentence_rate": settings.sentence_rate,
        "mode": mode,
        "text": text,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_tts_cache_path(text: str, mode: str, settings: TTSSettings) -> Path:
    cache_key = build_tts_cache_key(text, mode, settings)
    return TTS_CACHE_DIR / f"{cache_key}.{_cache_extension(settings.audio_encoding)}"


def _get_google_access_token() -> tuple[str, str | None]:
    try:
        import google.auth
        from google.auth import exceptions as google_auth_exceptions
        from google.auth.transport.requests import Request
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise TTSConfigurationError(
            "Google TTS requires the optional 'google-auth' package."
        ) from exc

    try:
        credentials, _ = google.auth.default(scopes=[GOOGLE_TTS_SCOPE])
        if not credentials.valid:
            credentials.refresh(Request())
    except google_auth_exceptions.RefreshError as exc:
        raise TTSConfigurationError(
            "Google TTS credentials expired. Run `gcloud auth application-default login` again."
        ) from exc
    except google_auth_exceptions.DefaultCredentialsError as exc:
        raise TTSConfigurationError(
            "Google TTS credentials are not configured correctly."
        ) from exc

    if not credentials.token:
        raise TTSConfigurationError("Google credentials did not return an access token.")

    return credentials.token, getattr(credentials, "quota_project_id", None)


def synthesize_google_tts(text: str, mode: str, settings: TTSSettings) -> bytes:
    token, quota_project_id = _get_google_access_token()
    payload = build_google_synthesis_payload(text, mode, settings)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    if quota_project_id:
        headers["x-goog-user-project"] = quota_project_id
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        GOOGLE_TTS_ENDPOINT,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise TTSProviderError(f"Google TTS request failed: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise TTSProviderError(f"Google TTS network error: {exc.reason}") from exc

    audio_content = data.get("audioContent")
    if not audio_content:
        raise TTSProviderError("Google TTS response did not include audio content.")

    return base64.b64decode(audio_content)


def synthesize_speech(text: str, mode: str = "word") -> tuple[bytes, str]:
    settings = load_tts_settings()

    if settings.provider != "google":
        raise TTSConfigurationError(
            "Server TTS is not enabled. Set TTS_PROVIDER=google to use Google Cloud Text-to-Speech."
        )

    cache_path = get_tts_cache_path(text, mode, settings)
    if cache_path.exists():
        audio = cache_path.read_bytes()
    else:
        audio = synthesize_google_tts(text, mode, settings)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(audio)

    media_type = "audio/mpeg" if settings.audio_encoding == "MP3" else "application/octet-stream"
    return audio, media_type
