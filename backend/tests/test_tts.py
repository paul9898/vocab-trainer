import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.tts import (
    TTSSettings,
    build_google_synthesis_payload,
    build_tts_cache_key,
    get_tts_cache_path,
    synthesize_speech,
)


class GoogleTTSPayloadTests(unittest.TestCase):
    def test_word_mode_uses_word_rate(self) -> None:
        settings = TTSSettings(
            provider="google",
            language_code="th-TH",
            voice_name="th-TH-Standard-A",
            audio_encoding="MP3",
            word_rate=0.81,
            sentence_rate=0.95,
        )

        payload = build_google_synthesis_payload("กิน", "word", settings)

        self.assertEqual(payload["input"]["text"], "กิน")
        self.assertEqual(payload["voice"]["name"], "th-TH-Standard-A")
        self.assertEqual(payload["audioConfig"]["audioEncoding"], "MP3")
        self.assertEqual(payload["audioConfig"]["speakingRate"], 0.81)

    def test_sentence_mode_uses_sentence_rate(self) -> None:
        settings = TTSSettings(
            provider="google",
            language_code="th-TH",
            voice_name="th-TH-Standard-A",
            audio_encoding="MP3",
            word_rate=0.81,
            sentence_rate=0.95,
        )

        payload = build_google_synthesis_payload("ฉันกินข้าว", "sentence", settings)

        self.assertEqual(payload["audioConfig"]["speakingRate"], 0.95)

    def test_tts_cache_key_changes_with_mode(self) -> None:
        settings = TTSSettings(provider="google")
        self.assertNotEqual(
            build_tts_cache_key("กิน", "word", settings),
            build_tts_cache_key("กิน", "sentence", settings),
        )

    def test_synthesize_speech_reuses_disk_cache(self) -> None:
        settings = TTSSettings(
            provider="google",
            language_code="th-TH",
            voice_name="th-TH-Standard-A",
            audio_encoding="MP3",
            word_rate=0.81,
            sentence_rate=0.95,
        )
        call_count = {"count": 0}

        def fake_google_tts(text: str, mode: str, active_settings: TTSSettings) -> bytes:
            call_count["count"] += 1
            self.assertEqual(text, "กิน")
            self.assertEqual(mode, "word")
            self.assertEqual(active_settings.voice_name, settings.voice_name)
            return b"fake-mp3"

        with TemporaryDirectory() as tempdir:
            with patch("backend.tts.load_tts_settings", return_value=settings), patch(
                "backend.tts.TTS_CACHE_DIR", Path(tempdir)
            ), patch("backend.tts.synthesize_google_tts", side_effect=fake_google_tts):
                first_audio, first_media_type = synthesize_speech("กิน", "word")
                second_audio, second_media_type = synthesize_speech("กิน", "word")

                self.assertEqual(first_audio, b"fake-mp3")
                self.assertEqual(second_audio, b"fake-mp3")
                self.assertEqual(first_media_type, "audio/mpeg")
                self.assertEqual(second_media_type, "audio/mpeg")
                self.assertEqual(call_count["count"], 1)
                self.assertTrue(get_tts_cache_path("กิน", "word", settings).exists())


if __name__ == "__main__":
    unittest.main()
