import asyncio
import json
import unittest

from engine.contracts import AudioChunk
from engine.integration import (
    EngineRuntime,
    LegacyProtocolAdapter,
    LegacySessionChannel,
    build_pipeline_from_config,
)
from engine.pipeline import AiPipeline
from engine.session import SessionRegistry
from engine.stubs import (
    AlwaysVoiceVAD,
    EchoASR,
    PaletteTTS,
    RuleLLM,
    register_standard_providers,
)
from engine.transport import Frame as TFrame
from engine.ws import WebSocketConnection


class BuildFromConfigTest(unittest.TestCase):
    def test_named_providers_no_warnings(self) -> None:
        pipeline, warnings = build_pipeline_from_config(
            {
                "selected_module": {
                    "ASR": "echo",
                    "LLM": "rule",
                    "TTS": "palette",
                    "VAD": "always_voice",
                }
            }
        )
        self.assertEqual(warnings, [])
        result = asyncio.run(
            pipeline.run_turn(AudioChunk(b"\x00" * 64), "s")
        )
        self.assertEqual(result.reply, "这是一个可插拔的 AI 编排引擎。")

    def test_missing_provider_falls_back(self) -> None:
        pipeline, warnings = build_pipeline_from_config({"selected_module": {}})
        self.assertGreaterEqual(len(warnings), 1)
        self.assertIn("回退", warnings[0])


class ProtocolAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = LegacyProtocolAdapter(device_id="dev-9")

    def test_decode_hello(self) -> None:
        frame = self.adapter.decode(
            json.dumps({"type": "hello", "audio_params": {"format": "opus"}})
        )
        self.assertEqual(frame.type, "hello")
        self.assertEqual(frame.metadata["device_id"], "dev-9")

    def test_decode_audio(self) -> None:
        frame = self.adapter.decode(b"\x00\x01")
        self.assertEqual(frame.type, "audio")
        self.assertEqual(frame.payload, b"\x00\x01")

    def test_encode_reply_and_audio(self) -> None:
        from engine.transport import Frame

        texts = self.adapter.encode(Frame("reply", metadata={"text": "好"}))
        self.assertEqual(json.loads(texts[0])["type"], "llm")
        binaries = self.adapter.encode(Frame("audio", payload=b"abc"))
        self.assertEqual(binaries, [b"abc"])


class FakeLegacyWS:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.texts = []
        self.binaries = []
        self.closed = False

    async def receive(self):
        return self.incoming.pop(0)

    async def send_text(self, text: str) -> None:
        self.texts.append(text)

    async def send_binary(self, data: bytes) -> None:
        self.binaries.append(data)

    async def close(self) -> None:
        self.closed = True


class LegacyChannelTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_legacy_turn(self) -> None:
        pipeline = AiPipeline(
            EchoASR(), RuleLLM(reply="集成回复"), PaletteTTS(), AlwaysVoiceVAD()
        )
        ws = FakeLegacyWS(
            [
                json.dumps({"type": "hello"}),
                b"\x00" * 320,
                json.dumps({"type": "bye"}),
            ]
        )
        channel = LegacySessionChannel(ws, pipeline, SessionRegistry())
        await channel.run()
        self.assertEqual(json.loads(ws.texts[0])["type"], "hello")
        self.assertEqual(json.loads(ws.texts[1])["type"], "listen")
        self.assertEqual(json.loads(ws.texts[2])["type"], "stt")
        self.assertEqual(json.loads(ws.texts[3])["type"], "llm")
        self.assertGreater(len(ws.binaries[0]), 0)


class RuntimeServeTest(unittest.IsolatedAsyncioTestCase):
    async def test_serve_with_legacy_protocol_over_real_ws(self) -> None:
        runtime = EngineRuntime(
            lambda: AiPipeline(
                EchoASR(), RuleLLM(reply="运行层回复"), PaletteTTS(), AlwaysVoiceVAD()
            )
        )
        server = await runtime.serve(port=0)
        try:
            conn = await WebSocketConnection.connect("127.0.0.1", server.port)
            await conn.send_text(json.dumps({"type": "hello"}))
            await conn.send_binary(b"\x00" * 320)
            messages = []
            for _ in range(5):
                messages.append(await asyncio.wait_for(conn.receive(), timeout=10))
            self.assertEqual(json.loads(messages[0])["type"], "hello")
            self.assertEqual(json.loads(messages[1])["type"], "listen")
            self.assertEqual(json.loads(messages[2])["type"], "stt")
            self.assertEqual(json.loads(messages[3])["type"], "llm")
            self.assertIsInstance(messages[4], bytes)
            await conn.send_text(json.dumps({"type": "bye"}))
            await conn.close()
        finally:
            await server.stop()

    def test_engine_providers_override_selected(self) -> None:
        pipeline, warnings = build_pipeline_from_config(
            {
                "selected_module": {"LLM": "failing"},
                "engine": {"providers": {"llm": {"name": "rule"}}},
            }
        )
        self.assertNotIn("LLM: 未找到可用实现", warnings)
        result = asyncio.run(pipeline.run_turn(AudioChunk(b"\x00" * 64), "s"))
        self.assertEqual(result.reply, "这是一个可插拔的 AI 编排引擎。")


if __name__ == "__main__":
    unittest.main()
