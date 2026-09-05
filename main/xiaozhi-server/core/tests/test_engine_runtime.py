import asyncio
import unittest

from core.engine_runtime import (
    LegacyWebSocketSurface,
    build_engine_pipeline,
    create_engine_channel,
    read_engine_mode,
)


class FakeWS:
    def __init__(self, incoming=None):
        self.incoming = list(incoming or [])
        self.sent = []
        self.closed = False

    async def recv(self):
        return self.incoming.pop(0)

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


class EngineModeTest(unittest.TestCase):
    def test_default_is_legacy(self) -> None:
        self.assertEqual(read_engine_mode({}), "legacy")
        self.assertEqual(read_engine_mode({"engine": {"mode": "AUTO"}}), "auto")
        self.assertEqual(read_engine_mode({"engine": {"mode": "bad"}}), "legacy")

    def test_provider_config_resolution(self) -> None:
        pipeline, warnings = build_engine_pipeline(
            {
                "engine": {
                    "providers": {
                        "asr": {"name": "echo"},
                        "llm": {"name": "rule"},
                        "tts": {"name": "palette"},
                        "vad": {"name": "always_voice"},
                    }
                }
            }
        )
        self.assertEqual(warnings, [])
        self.assertIsNotNone(pipeline)

    def test_missing_provider_returns_warning(self) -> None:
        pipeline, warnings = build_engine_pipeline(
            {"engine": {"providers": {"llm": {"name": "missing"}}}}
        )
        self.assertGreater(len(warnings), 0)

    def test_channel_created_only_when_resolved(self) -> None:
        ws = FakeWS()
        channel = create_engine_channel(
            ws,
            {
                "engine": {
                    "providers": {
                        "asr": {"name": "echo"},
                        "llm": {"name": "rule"},
                        "tts": {"name": "palette"},
                        "vad": {"name": "always_voice"},
                    }
                }
            },
        )
        self.assertIsNotNone(channel)
        bad = create_engine_channel(ws, {"engine": {"providers": {}}})
        self.assertIsNone(bad)


class SurfaceTest(unittest.IsolatedAsyncioTestCase):
    async def test_surface_roundtrip(self) -> None:
        ws = FakeWS(["hello", b"audio"])
        surface = LegacyWebSocketSurface(ws, device_id="d1")
        self.assertEqual(await surface.receive(), "hello")
        self.assertEqual(await surface.receive(), b"audio")
        await surface.send_text("x")
        await surface.send_binary(b"y")
        await surface.close()
        self.assertEqual(ws.sent, ["x", b"y"])
        self.assertTrue(ws.closed)


if __name__ == "__main__":
    unittest.main()
