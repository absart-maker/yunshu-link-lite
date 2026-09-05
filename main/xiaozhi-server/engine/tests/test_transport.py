import asyncio
import unittest

from engine.pipeline import AiPipeline
from engine.session import SessionRegistry
from engine.stubs import AlwaysVoiceVAD, EchoASR, PaletteTTS, RuleLLM
from engine.transport import (
    Frame,
    InMemoryTransport,
    JsonFrameCodec,
    RealtimeDeviceChannel,
)


def make_pipeline():
    return AiPipeline(
        EchoASR(),
        RuleLLM(reply="输出"),
        PaletteTTS(),
        AlwaysVoiceVAD(),
    )


class JsonFrameCodecTest(unittest.TestCase):
    def test_roundtrip_text_payload(self) -> None:
        codec = JsonFrameCodec()
        raw = codec.encode(Frame("reply", b"hello", {"k": 1}))
        frame = codec.decode(raw)
        self.assertEqual(frame.type, "reply")
        self.assertEqual(frame.payload, b"hello")
        self.assertEqual(frame.metadata["k"], 1)

    def test_roundtrip_binary_payload(self) -> None:
        codec = JsonFrameCodec()
        frame = codec.decode(
            b'{"type":"audio","payload":"\\u0001\\u0002","meta":{}}'
        )
        self.assertEqual(frame.payload, b"\x01\x02")


class RealtimeChannelTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_audio_turn(self) -> None:
        transport = InMemoryTransport()
        codec = JsonFrameCodec()
        channel = RealtimeDeviceChannel(
            transport, make_pipeline(), SessionRegistry(), codec
        )
        task = asyncio.create_task(channel.run())
        transport.push_raw(codec.encode(Frame("hello", metadata={"device_id": "d1"})))
        transport.push_raw(
            codec.encode(Frame("audio", b"\x00" * 320, {"sample_rate": 16000}))
        )

        async def wait_for_frames(count: int) -> None:
            for _ in range(100):
                if len(transport.outgoing) >= count:
                    return
                await asyncio.sleep(0.01)
            self.fail("未等到足够的输出帧")

        await wait_for_frames(5)
        types = [codec.decode(raw).type for raw in transport.outgoing]
        self.assertEqual(types[:5], ["ready", "listening", "transcript", "reply", "audio"])

        transport.push_raw(codec.encode(Frame("bye")))
        await asyncio.wait_for(task, timeout=1)
        self.assertTrue(transport.closed)

    async def test_audio_before_hello_rejected(self) -> None:
        transport = InMemoryTransport()
        codec = JsonFrameCodec()
        channel = RealtimeDeviceChannel(transport, make_pipeline(), SessionRegistry(), codec)
        task = asyncio.create_task(channel.run())
        transport.push_raw(codec.encode(Frame("audio", b"\x00" * 320)))
        await asyncio.sleep(0.05)
        types = [codec.decode(raw).type for raw in transport.outgoing]
        self.assertIn("error", types)
        task.cancel()

    async def test_unknown_frame_gets_error(self) -> None:
        transport = InMemoryTransport()
        codec = JsonFrameCodec()
        channel = RealtimeDeviceChannel(transport, make_pipeline(), SessionRegistry(), codec)
        task = asyncio.create_task(channel.run())
        transport.push_raw(codec.encode(Frame("weird")))
        await asyncio.sleep(0.05)
        types = [codec.decode(raw).type for raw in transport.outgoing]
        self.assertIn("error", types)
        task.cancel()

    async def test_abort_stops_channel(self) -> None:
        transport = InMemoryTransport()
        codec = JsonFrameCodec()
        channel = RealtimeDeviceChannel(transport, make_pipeline(), SessionRegistry(), codec)
        task = asyncio.create_task(channel.run())
        transport.push_raw(codec.encode(Frame("hello", metadata={"device_id": "a"})))
        transport.push_raw(codec.encode(Frame("abort")))
        await asyncio.wait_for(task, timeout=1)
        types = [codec.decode(raw).type for raw in transport.outgoing]
        self.assertIn("aborted", types)
        self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
