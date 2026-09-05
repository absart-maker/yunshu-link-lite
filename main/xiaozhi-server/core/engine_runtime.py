"""旧服务到新引擎的可切换运行层。

配置项（data/.config.yaml）:
    engine:
      mode: legacy | engine | auto

- legacy：保持原有 ConnectionHandler 行为（默认）。
- engine：强制使用原创引擎服务；失败则拒绝连接并记录错误。
- auto：引擎可用则接管，不可用则回退旧处理器。

引擎仅在以下情况接管：`engine.providers`（或 selected_module）中的
ASR/LLM/TTS/VAD 均在注册表中解析成功。缺失时返回 None，避免静默用
参考实现替换真实模型。
"""

from __future__ import annotations

from typing import Any, Optional


def read_engine_mode(config: dict[str, Any]) -> str:
    mode = str(config.get("engine", {}).get("mode", "legacy")).lower()
    if mode not in ("legacy", "engine", "auto"):
        return "legacy"
    return mode


class LegacyWebSocketSurface:
    """把 websockets ServerConnection 适配为旧协议通道所需接口。"""

    def __init__(self, websocket, device_id: str = "") -> None:
        self.ws = websocket
        self.device_id = device_id

    async def receive(self) -> str | bytes:
        return await self.ws.recv()

    async def send_text(self, text: str) -> None:
        await self.ws.send(text)

    async def send_binary(self, data: bytes) -> None:
        await self.ws.send(data)

    async def close(self) -> None:
        await self.ws.close()


def build_engine_pipeline(config: dict[str, Any]):
    """尝试装配引擎；返回 (pipeline, warnings)。"""

    from engine.integration import build_pipeline_from_config

    return build_pipeline_from_config(config)


def create_engine_channel(websocket, config: dict[str, Any], *, device_id: str = "", registry=None):
    """创建旧协议引擎通道；无法完整解析 Provider 时返回 None。"""

    pipeline, warnings = build_engine_pipeline(config)
    if warnings:
        return None
    from engine.integration import LegacyProtocolAdapter, LegacySessionChannel
    from engine.session import SessionRegistry

    surface = LegacyWebSocketSurface(websocket, device_id=device_id)
    return LegacySessionChannel(
        surface,
        pipeline,
        registry or SessionRegistry(),
        adapter=LegacyProtocolAdapter(device_id=device_id),
    )
