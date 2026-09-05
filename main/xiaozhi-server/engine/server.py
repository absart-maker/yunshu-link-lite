"""真实网络服务入口：以 WebSocket 运行原创引擎。

用法:
    python -m engine.server --port 8765         # 启动服务
    python -m engine.server --client --port 8765  # 客户端验收
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from .pipeline import AiPipeline
from .session import SessionRegistry
from .stubs import AlwaysVoiceVAD, EchoASR, PaletteTTS, RuleLLM
from .transport import Frame, JsonFrameCodec, RealtimeServer
from .ws import WebSocketConnection, WebSocketServer


def build_realtime() -> RealtimeServer:
    def factory() -> AiPipeline:
        return AiPipeline(
            EchoASR(),
            RuleLLM(reply="真实服务回复"),
            PaletteTTS(),
            AlwaysVoiceVAD(),
        )

    return RealtimeServer(SessionRegistry(), factory)


async def run_server(port: int, host: str = "127.0.0.1") -> None:
    realtime = build_realtime()
    ws_server = WebSocketServer(realtime.handle_connection, host=host, port=port)
    await ws_server.start()
    print(f"engine server listening on ws://{host}:{ws_server.port}/", flush=True)
    try:
        await asyncio.Future()
    finally:
        await ws_server.stop()


async def run_client(port: int, host: str = "127.0.0.1") -> list[Frame]:
    codec = JsonFrameCodec()
    conn = await WebSocketConnection.connect(host, port)
    await conn.send(codec.encode(Frame("hello", metadata={"device_id": "cli-1"})))
    await conn.send(
        codec.encode(Frame("audio", b"\x00" * 3200, {"sample_rate": 16000}))
    )
    frames = []
    for _ in range(5):
        frames.append(codec.decode(await asyncio.wait_for(conn.receive(), timeout=10)))
    await conn.send(codec.encode(Frame("bye")))
    await conn.close()
    return frames


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="engine WebSocket 服务")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--client", action="store_true", help="以客户端模式验收")
    args = parser.parse_args()
    if args.client:
        frames = asyncio.run(run_client(args.port, args.host))
        print(" -> ".join(frame.type for frame in frames), flush=True)
    else:
        asyncio.run(run_server(args.port, args.host))


if __name__ == "__main__":
    main()
