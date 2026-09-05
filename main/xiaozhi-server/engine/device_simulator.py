"""模拟设备客户端：完整走一遍实时设备协议。

用法:
    python -m engine.device_simulator

流程:
    ready <- hello -> listening -> transcript -> reply -> audio -> bye
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .contracts import AudioChunk
from .pipeline import AiPipeline
from .session import SessionRegistry
from .stubs import AlwaysVoiceVAD, EchoASR, PaletteTTS, RuleLLM
from .transport import (
    AsyncTransport,
    Frame,
    FrameCodec,
    InMemoryTransport,
    JsonFrameCodec,
    RealtimeServer,
)


class LoopbackTransport:
    """与对端共享队列的内存传输，客户端/服务端成对使用。"""

    def __init__(self, peer: "LoopbackTransport" | None = None) -> None:
        self.incoming = asyncio.Queue()
        self.peer = peer
        self.closed = False

    def connect(self, peer: "LoopbackTransport") -> None:
        self.peer = peer
        peer.peer = self

    async def send(self, raw: bytes) -> None:
        if self.peer is not None:
            self.peer.incoming.put_nowait(raw)

    async def receive(self) -> bytes:
        return await self.incoming.get()

    async def close(self) -> None:
        self.closed = True


def connect_pair() -> tuple[LoopbackTransport, LoopbackTransport]:
    client = LoopbackTransport()
    server = LoopbackTransport()
    client.connect(server)
    return client, server


class DeviceSimulator:
    def __init__(
        self,
        server: RealtimeServer,
        *,
        device_id: str = "sim-1",
        pcm: bytes = b"\x00" * 3200,
        sample_rate: int = 16000,
    ) -> None:
        self.server = server
        self.device_id = device_id
        self.pcm = pcm
        self.sample_rate = sample_rate
        self.codec: FrameCodec = JsonFrameCodec()

    async def run(self) -> list[Frame]:
        client, server_transport = connect_pair()
        server_task = asyncio.create_task(
            self.server.handle_connection(server_transport)
        )
        received: list[Frame] = []

        await client.send(
            self.codec.encode(Frame("hello", metadata={"device_id": self.device_id}))
        )
        await client.send(
            self.codec.encode(
                Frame(
                    "audio",
                    self.pcm,
                    {"sample_rate": self.sample_rate},
                )
            )
        )

        for _ in range(5):
            received.append(
                self.codec.decode(await asyncio.wait_for(client.receive(), timeout=10))
            )

        await client.send(self.codec.encode(Frame("bye")))
        await asyncio.wait_for(server_task, timeout=5)
        return received


def default_server() -> RealtimeServer:
    def factory() -> AiPipeline:
        return AiPipeline(
            EchoASR(),
            RuleLLM(reply="设备模拟回复"),
            PaletteTTS(),
            AlwaysVoiceVAD(),
        )

    return RealtimeServer(SessionRegistry(), factory)


async def _main() -> None:
    server = default_server()
    frames = await DeviceSimulator(server).run()
    for frame in frames:
        text = ""
        if frame.type in ("transcript", "reply"):
            text = frame.metadata.get("text", "")
        elif frame.type == "audio":
            text = f"{len(frame.payload)} bytes"
        print(f"{frame.type}: {text}", flush=True)


if __name__ == "__main__":
    asyncio.run(_main())
