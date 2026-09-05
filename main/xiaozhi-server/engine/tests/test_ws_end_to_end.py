import asyncio
import unittest

from engine.server import build_realtime
from engine.transport import Frame, JsonFrameCodec
from engine.ws import WebSocketConnection, WebSocketServer


class WebSocketEndToEndTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.realtime = build_realtime()
        self.server = WebSocketServer(self.realtime.handle_connection)
        await self.server.start()
        self.port = self.server.port

    async def asyncTearDown(self) -> None:
        await self.server.stop()

    async def test_real_websocket_full_turn(self) -> None:
        codec = JsonFrameCodec()
        conn = await WebSocketConnection.connect("127.0.0.1", self.port)
        await conn.send(codec.encode(Frame("hello", metadata={"device_id": "e2e"})))
        await conn.send(
            codec.encode(Frame("audio", b"\x00" * 3200, {"sample_rate": 16000}))
        )
        types = []
        for _ in range(5):
            frame = codec.decode(
                await asyncio.wait_for(conn.receive(), timeout=10)
            )
            types.append(frame.type)
        await conn.send(codec.encode(Frame("bye")))
        await conn.close()
        self.assertEqual(
            types,
            ["ready", "listening", "transcript", "reply", "audio"],
        )


if __name__ == "__main__":
    unittest.main()
