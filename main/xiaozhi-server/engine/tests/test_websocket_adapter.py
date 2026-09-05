import unittest

from engine.bridge.websocket import WebSocketTransport


class FakeWebSocket:
    def __init__(self, incoming=None):
        self.incoming = list(incoming or [])
        self.sent = []
        self.closed = False

    async def send(self, raw: bytes) -> None:
        self.sent.append(raw)

    async def recv(self) -> bytes:
        return self.incoming.pop(0) if self.incoming else b""

    async def close(self) -> None:
        self.closed = True


class WebSocketAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_send_receive_close(self) -> None:
        ws = FakeWebSocket([b"hello"])
        transport = WebSocketTransport(ws)
        received = await transport.receive()
        self.assertEqual(received, b"hello")
        await transport.send(b"world")
        self.assertEqual(ws.sent, [b"world"])
        await transport.close()
        self.assertTrue(ws.closed)


if __name__ == "__main__":
    unittest.main()
