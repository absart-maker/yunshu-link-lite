"""极简 WebSocket 实现（仅标准库）。

提供服务器端与客户端共用的连接对象：握手、帧编解码、ping/pong 与关闭，
让原创引擎可以以真实网络服务方式运行，无需第三方依赖。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import struct
from typing import Awaitable, Callable

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class ConnectionClosed(Exception):
    pass


class WebSocketConnection:
    """支持客户端/服务端两种形态的 WebSocket 连接。"""

    def __init__(self, reader, writer, *, mask_outgoing: bool = False) -> None:
        self._reader = reader
        self._writer = writer
        self._mask_outgoing = mask_outgoing
        self.closed = False

    @classmethod
    async def connect(cls, host: str, port: int) -> "WebSocketConnection":
        reader, writer = await asyncio.open_connection(host, port)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        writer.write(request.encode())
        await writer.drain()
        response = await reader.readuntil(b"\r\n\r\n")
        if not response.startswith(b"HTTP/1.1 101"):
            writer.close()
            raise ConnectionError("WebSocket 握手失败")
        return cls(reader, writer, mask_outgoing=True)

    async def send(self, raw: bytes) -> None:
        await self._send_frame(0x2, raw)

    async def send_text(self, text: str) -> None:
        await self._send_frame(0x1, text.encode("utf-8"))

    async def send_binary(self, data: bytes) -> None:
        await self._send_frame(0x2, data)

    async def receive(self) -> bytes:
        buffer = bytearray()
        while True:
            header = await self._reader.readexactly(2)
            fin = bool(header[0] & 0x80)
            opcode = header[0] & 0x0F
            masked = bool(header[1] & 0x80)
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", await self._reader.readexactly(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", await self._reader.readexactly(8))[0]
            if length > 2**24:
                raise ConnectionError("帧过大")

            mask = await self._reader.readexactly(4) if masked else b""
            payload = await self._reader.readexactly(length) if length else b""
            if masked:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )

            if opcode == 0x8:
                await self._send_frame(0x8, b"")
                self.closed = True
                raise ConnectionClosed()
            if opcode == 0x9:
                await self._send_frame(0xA, payload)
                continue
            if opcode == 0x0:
                buffer.extend(payload)
                if fin:
                    return bytes(buffer)
                continue
            if opcode in (0x1, 0x2):
                if not fin:
                    buffer.extend(payload)
                    continue
                if opcode == 0x1:
                    return payload.decode("utf-8")
                return payload
            raise ConnectionError(f"未知 opcode: {opcode}")

    async def close(self) -> None:
        if self.closed:
            return
        try:
            await self._send_frame(0x8, b"")
        finally:
            self.closed = True
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.append(126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(127)
            header.extend(struct.pack(">Q", length))
        if self._mask_outgoing:
            mask = b"\x01\x02\x03\x04"
            header[1] |= 0x80
            header.extend(mask)
            payload = bytes(
                byte ^ mask[index % 4] for index, byte in enumerate(payload)
            )
        self._writer.write(bytes(header) + payload)
        await self._writer.drain()


async def server_handshake(reader, writer) -> None:
    request = await reader.readuntil(b"\r\n\r\n")
    headers = {}
    for line in request.decode(errors="replace").split("\r\n")[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    key = headers.get("sec-websocket-key")
    if not key:
        writer.close()
        raise ConnectionError("缺少 Sec-WebSocket-Key")
    accept = base64.b64encode(
        hashlib.sha1((key + GUID).encode()).digest()
    ).decode()
    writer.write(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode()
    )
    await writer.drain()


class WebSocketServer:
    """监听端口并升级连接的极简服务器。"""

    def __init__(
        self,
        handler: Callable[[WebSocketConnection], Awaitable[None]],
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.handler = handler
        self.host = host
        self.port = port
        self._server = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._accept, self.host, self.port)
        sock = self._server.sockets[0]
        self.port = sock.getsockname()[1]

    async def _accept(self, reader, writer) -> None:
        conn = None
        try:
            await server_handshake(reader, writer)
            conn = WebSocketConnection(reader, writer)
            await self.handler(conn)
        except (ConnectionError, ConnectionClosed):
            pass
        except Exception:
            pass
        finally:
            if conn is not None:
                await conn.close()
            else:
                writer.close()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
