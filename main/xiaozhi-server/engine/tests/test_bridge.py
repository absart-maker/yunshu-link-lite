import asyncio
import unittest

from engine.bridge import (
    FunctionSpeechToText,
    LegacyLanguageModel,
    LegacyTextToSpeech,
    LegacyVoiceActivityDetector,
    StreamingTextToSpeech,
)
from engine.contracts import AudioChunk, Message


class FakeLegacyLLM:
    def response(self, session_id, dialogue):
        return ["你", "好"]


class FakeLegacyVAD:
    def is_vad(self, conn, pcm_frame):
        return len(pcm_frame) > 0


class FakeLegacyTTS:
    def to_tts(self, text):
        return b"pcm-" + text.encode("utf-8")


class FakeLegacyStreamTTS:
    def to_tts_stream(self, text, handler):
        handler(b"a")
        handler(b"b")


class BridgeTest(unittest.TestCase):
    def test_legacy_llm_reply(self) -> None:
        model = LegacyLanguageModel(FakeLegacyLLM())
        chunks = asyncio.run(
            _collect(model.stream_reply([Message("user", "hi")], "s1"))
        )
        self.assertEqual(chunks, "你好")

    def test_legacy_vad(self) -> None:
        detector = LegacyVoiceActivityDetector(FakeLegacyVAD())
        self.assertTrue(detector.is_speech(AudioChunk(b"\x01\x02")))
        self.assertFalse(detector.is_speech(AudioChunk(b"")))

    def test_legacy_tts_bridge(self) -> None:
        tts = LegacyTextToSpeech(FakeLegacyTTS())
        chunks = asyncio.run(
            _collect_tts(tts.synthesize("你好", "s1"))
        )
        self.assertEqual(chunks, b"pcm-\xe4\xbd\xa0\xe5\xa5\xbd")

    def test_streaming_tts_bridge(self) -> None:
        tts = StreamingTextToSpeech(FakeLegacyStreamTTS())
        chunks = asyncio.run(_collect_tts(tts.synthesize("x", "s1")))
        self.assertEqual(chunks, b"ab")

    def test_function_asr_sync_and_async(self) -> None:
        sync = FunctionSpeechToText(lambda pcm: "同步结果")
        result = asyncio.run(sync.transcribe(AudioChunk(b"x"), "s1"))
        self.assertEqual(result.text, "同步结果")


async def _collect(iterator):
    return "".join([chunk.text async for chunk in iterator])


async def _collect_tts(iterator):
    return b"".join([chunk.pcm async for chunk in iterator])


if __name__ == "__main__":
    unittest.main()
