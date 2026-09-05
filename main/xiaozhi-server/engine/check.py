"""一键自检入口。

用法（在 main/xiaozhi-server 目录下）:
    python -m engine.check

执行：全量单元测试 + 端到端演示 + 模拟设备协议实测。
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


def run_unit_tests() -> tuple[bool, int]:
    engine_dir = Path(__file__).resolve().parent
    top_dir = str(engine_dir.parent)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(
        loader.discover(str(engine_dir / "tests"), top_level_dir=top_dir)
    )
    suite.addTests(
        loader.discover(str(engine_dir.parent / "core" / "tests"), top_level_dir=top_dir)
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful(), result.testsRun


async def _scenarios() -> bool:
    ok = True
    from .demo import _run

    try:
        await _run(str(Path(__file__).parent / "examples" / "demo.json"))
        print("[CHECK] 端到端演示: PASS", flush=True)
    except Exception as exc:  # pragma: no cover - 保护性捕获
        print(f"[CHECK] 端到端演示: FAIL ({exc})", flush=True)
        ok = False

    try:
        from .device_simulator import DeviceSimulator, default_server

        frames = await DeviceSimulator(default_server()).run()
        types = [frame.type for frame in frames]
        expected = ["ready", "listening", "transcript", "reply", "audio"]
        passed = types[:5] == expected
        print(
            f"[CHECK] 模拟设备协议: {'PASS' if passed else 'FAIL'} ({' -> '.join(types)})",
            flush=True,
        )
        ok = ok and passed
    except Exception as exc:  # pragma: no cover - 保护性捕获
        print(f"[CHECK] 模拟设备协议: FAIL ({exc})", flush=True)
        ok = False

    try:
        from .server import build_realtime
        from .transport import Frame, JsonFrameCodec
        from .ws import WebSocketConnection, WebSocketServer

        server = WebSocketServer(build_realtime().handle_connection)
        await server.start()
        try:
            codec = JsonFrameCodec()
            conn = await WebSocketConnection.connect("127.0.0.1", server.port)
            await conn.send(
                codec.encode(Frame("hello", metadata={"device_id": "check"}))
            )
            await conn.send(
                codec.encode(
                    Frame("audio", b"\x00" * 3200, {"sample_rate": 16000})
                )
            )
            types = []
            for _ in range(5):
                frame = codec.decode(
                    await asyncio.wait_for(conn.receive(), timeout=10)
                )
                types.append(frame.type)
            await conn.send(codec.encode(Frame("bye")))
            await conn.close()
            expected = ["ready", "listening", "transcript", "reply", "audio"]
            passed = types == expected
            print(
                f"[CHECK] WebSocket 服务实测: {'PASS' if passed else 'FAIL'} ({' -> '.join(types)})",
                flush=True,
            )
            ok = ok and passed
        finally:
            await server.stop()
    except Exception as exc:  # pragma: no cover - 保护性捕获
        print(f"[CHECK] WebSocket 服务实测: FAIL ({exc})", flush=True)
        ok = False

    return ok


def main() -> int:
    print("[CHECK] 单元测试 ...", flush=True)
    tests_ok, test_count = run_unit_tests()
    print(f"[CHECK] 单元测试: {test_count}/{test_count} 通过", flush=True)
    scenario_ok = asyncio.run(_scenarios())
    if tests_ok and scenario_ok:
        print("[CHECK] 全部通过: PASS", flush=True)
        return 0
    print("[CHECK] 存在失败项: FAIL", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
