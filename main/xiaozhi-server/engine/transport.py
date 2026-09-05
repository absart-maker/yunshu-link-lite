"""实时设备会话层：传输、帧协议与设备通道的原创实现。

本层把“一条设备连接”抽象成：

  AsyncTransport  <->  FrameCodec  <->  RealtimeDeviceChannel
                                             |
                                        AiPipeline + SessionRegistry

传输实现（WebSocket、串口、TCP）只需实现 `send/receive/close`，
协议换用别的帧格式只需替换 `FrameCodec`，业务编排与传输完全解耦。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable

from .contracts import AudioChunk
from .pipeline import AiPipeline
from .session import SessionRegistry


@dataclass(frozen=True)
class Frame:
    type: str
    payload: bytes = b""
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class FrameCodec(Protocol):
    def encode(self, frame: Frame) -> bytes: ...

    def decode(self, raw: bytes) -> Frame: ...


class JsonFrameCodec:
    """JSON 信封帧：`{"type":..., "payload":..., "meta":...}`。"""

    def encode(self, frame: Frame) -> bytes:
        envelope = {
            "type": frame.type,
            "payload": base64_or_text(frame.payload),
            "meta": frame.metadata,
        }
        return json.dumps(envelope, ensure_ascii=False).encode("utf-8")

    def decode(self, raw: bytes) -> Frame:
        envelope = json.loads(raw.decode("utf-8"))
        payload = envelope.get("payload", "")
        if isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = bytes(payload or b"")
        return Frame(
            type=str(envelope.get("type", "")),
            payload=data,
            metadata=dict(envelope.get("meta", {})),
        )


def base64_or_text(data: bytes) -> str:
    """把二进制载荷统一encode为文本，避免 JSON 跨传输层失真。"""

    return data.decode("utf-8", errors="replace")


@runtime_checkable
class AsyncTransport(Protocol):
    async def send(self, raw: bytes) -> None: ...

    async def receive(self) -> bytes: ...

    async def close(self) -> None: ...


class InMemoryTransport:
    """字节级内存队列传输，用于测试与本地演示。"""

    def __init__(self, incoming: asyncio.Queue[bytes] | None = None) -> None:
        self.incoming = incoming or asyncio.Queue()
        self.outgoing: list[bytes] = []
        self.closed = False

    def push_raw(self, raw: bytes) -> None:
        self.incoming.put_nowait(raw)

    async def send(self, raw: bytes) -> None:
        self.outgoing.append(raw)

    async def receive(self) -> bytes:
        return await self.incoming.get()

    async def close(self) -> None:
        self.closed = True


class RealtimeDeviceChannel:
    """一条设备连接的会话编排器。"""

    def __init__(
        self,
        transport: AsyncTransport,
        pipeline: AiPipeline,
        registry: SessionRegistry,
        codec: FrameCodec | None = None,
    ) -> None:
        self.transport = transport
        self.pipeline = pipeline
        self.registry = registry
        self.codec = codec or JsonFrameCodec()
        self.session = None
        self._running = True

    async def run(self) -> None:
        await self._send("ready", {"server": "engine-v1"})
        try:
            while self._running:
                raw = await self.transport.receive()
                frame = self.codec.decode(raw)
                await self._dispatch(frame)
        finally:
            await self.transport.close()

    async def _dispatch(self, frame: Frame) -> None:
        if frame.type == "hello":
            self._open_session(frame)
        elif frame.type == "audio":
            await self._handle_audio(frame)
        elif frame.type == "abort":
            await self._send("aborted", {"session": self._session_id()})
            self._running = False
        elif frame.type == "bye":
            self._running = False
        else:
            await self._send("error", {"message": f"未知帧类型: {frame.type}"})

    def _open_session(self, frame: Frame) -> None:
        device_id = str(frame.metadata.get("device_id", ""))
        self.session = self.registry.create(device_id=device_id)

    async def _handle_audio(self, frame: Frame) -> None:
        if self.session is None:
            await self._send("error", {"message": "未握手，先发送 hello"})
            return
        audio = AudioChunk(
            pcm=frame.payload,
            sample_rate=int(frame.metadata.get("sample_rate", 16000)),
        )
        await self._send("listening", {"session": self.session.id})
        result = await self.pipeline.run_turn(
            audio,
            session_id=self.session.id,
            conversation=self.session.conversation,
        )
        await self._send("transcript", {"text": result.transcript})
        await self._send(
            "reply",
            {
                "text": result.reply,
                "metrics": result.metrics,
            },
        )
        if result.speech:
            await self._send(
                "audio",
                {"session": self.session.id},
                result.speech,
            )

    async def _send(self, frame_type: str, metadata: dict[str, object] | None = None, payload: bytes = b"") -> None:
        frame = Frame(frame_type, payload, metadata or {})
        await self.transport.send(self.codec.encode(frame))

    def _session_id(self) -> str:
        return self.session.id if self.session else ""


class RealtimeServer:
    """会话分发服务：为每条传输创建一个设备通道。"""

    def __init__(
        self,
        registry: SessionRegistry,
        pipeline_factory,
        codec: FrameCodec | None = None,
    ) -> None:
        self.registry = registry
        self.pipeline_factory = pipeline_factory
        self.codec = codec or JsonFrameCodec()

    async def handle_connection(self, transport: AsyncTransport) -> None:
        channel = RealtimeDeviceChannel(
            transport,
            self.pipeline_factory(),
            self.registry,
            self.codec,
        )
        await channel.run()
