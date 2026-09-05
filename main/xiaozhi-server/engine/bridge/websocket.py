"""WebSocket 传输适配器。

把符合 websockets 库连接形态的对象（具备 async `send`/`recv`/`close`）
适配为引擎的 `AsyncTransport`，从而让原创实时会话层直接服务设备。
"""

from __future__ import annotations

from typing import Any

from ..transport import AsyncTransport


class WebSocketTransport:
    """websockets 连接 -> AsyncTransport。"""

    def __init__(self, websocket: Any) -> None:
        self._ws = websocket

    async def send(self, raw: bytes) -> None:
        await self._ws.send(raw)

    async def receive(self) -> bytes:
        return await self._ws.recv()

    async def close(self) -> None:
        await self._ws.close()

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        return await self.receive()


class WebSocketTransportFactory:
    """按连接对象创建适配器的工厂，供 RealtimeServer 使用。"""

    def __call__(self, websocket: Any) -> WebSocketTransport:
        return WebSocketTransport(websocket)
