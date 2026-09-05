"""集成层：旧配置/协议与新引擎之间的接线。

1. `build_pipeline_from_config`：按旧 `selected_module` 组装引擎，
   可用 Provider 走注册表，缺失时回退到标准参考实现并返回警告。
2. `LegacyProtocolAdapter`：旧 WebSocket 消息（JSON 控制 + 二进制音频）
   与引擎 `Frame` 的双向转换。
3. `LegacySessionChannel`：用旧协议驱动一次完整引擎交互。
4. `EngineRuntime`：一键启动真实 WebSocket 服务，服务旧设备协议。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .contracts import AudioChunk
from .pipeline import AiPipeline
from .session import SessionRegistry
from .stubs import (
    AlwaysVoiceVAD,
    EchoASR,
    PaletteTTS,
    RuleLLM,
    register_standard_providers,
)
from .transport import Frame
from .ws import WebSocketServer


STUB_MAP = {
    "asr": EchoASR,
    "llm": RuleLLM,
    "tts": PaletteTTS,
    "vad": AlwaysVoiceVAD,
}


def build_pipeline_from_config(
    config: dict[str, Any],
    registry=None,
) -> tuple[AiPipeline, list[str]]:
    """按旧配置组装引擎，返回 (pipeline, warnings)。"""

    registry = registry or register_standard_providers()
    selected = config.get("selected_module", {})
    engine_providers = config.get("engine", {}).get("providers", {})
    warnings: list[str] = []

    def resolve(category: str) -> Any:
        cat_lower = category.lower()
        if engine_providers and cat_lower in engine_providers:
            item = engine_providers[cat_lower]
            name = item.get("name", "")
            options = item.get("options", {})
            if name and registry.has(cat_lower, name):
                return registry.create(cat_lower, name, options=options)
        name = selected.get(category.upper(), "")
        if name and registry.has(cat_lower, name):
            options = config.get(category, {}).get(name, {}).get("options", {})
            return registry.create(cat_lower, name, options=options)
        fallback = STUB_MAP.get(cat_lower)
        if fallback is not None:
            warnings.append(f"{category}: 未找到可用实现，已回退到标准参考实现")
            return fallback()
        raise ValueError(f"没有可用的 {category} 实现")

    return (
        AiPipeline(
            resolve("ASR"),
            resolve("LLM"),
            resolve("TTS"),
            resolve("VAD"),
        ),
        warnings,
    )


class LegacyProtocolAdapter:
    """旧协议 <-> 引擎帧转换。"""

    def __init__(self, device_id: str = "") -> None:
        self.device_id = device_id

    def decode(self, raw: str | bytes) -> Frame:
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"type": "text", "content": raw}
            msg_type = str(data.get("type", "unknown"))
            if msg_type == "hello":
                return Frame(
                    "hello",
                    metadata={
                        "device_id": self.device_id,
                        "audio_params": data.get("audio_params", {}),
                        "features": data.get("features", {}),
                    },
                )
            return Frame("control", payload=raw.encode("utf-8"), metadata=data)
        return Frame("audio", payload=raw)

    def encode(self, frame: Frame) -> list[str | bytes]:
        """引擎帧 -> 旧协议可发送的文本/二进制列表。"""

        if frame.type == "ready":
            return [json.dumps({"type": "hello", "state": "ready"})]
        if frame.type == "listening":
            return [json.dumps({"type": "listen", "state": "listening"})]
        if frame.type == "transcript":
            return [
                json.dumps({"type": "stt", "text": frame.metadata.get("text", "")})
            ]
        if frame.type == "reply":
            return [
                json.dumps({"type": "llm", "text": frame.metadata.get("text", "")})
            ]
        if frame.type == "audio":
            return [frame.payload]
        if frame.type == "error":
            return [
                json.dumps({"type": "error", "message": str(frame.metadata)})
            ]
        return []


class LegacySessionChannel:
    """用旧协议驱动一次完整引擎交互。"""

    STOP_TYPES = {"abort", "stop", "bye", "exit"}

    def __init__(
        self,
        legacy_ws,
        pipeline: AiPipeline,
        registry: SessionRegistry,
        adapter: LegacyProtocolAdapter | None = None,
    ) -> None:
        self.ws = legacy_ws
        self.pipeline = pipeline
        self.registry = registry
        self.adapter = adapter or LegacyProtocolAdapter()

    async def run(self) -> None:
        await self._send(Frame("ready"))
        session = None
        while True:
            raw = await self.ws.receive()
            frame = self.adapter.decode(raw)
            if frame.type == "hello":
                session = self.registry.create(
                    device_id=str(frame.metadata.get("device_id", ""))
                )
                continue
            if frame.type == "audio" and session is not None:
                await self._handle_audio(frame, session)
                continue
            if frame.type == "control":
                control_type = frame.metadata.get("type")
                if control_type in self.STOP_TYPES:
                    break

    async def _handle_audio(self, frame: Frame, session) -> None:
        await self._send(Frame("listening"))
        audio = AudioChunk(
            pcm=frame.payload,
            sample_rate=int(frame.metadata.get("sample_rate", 16000)),
        )
        result = await self.pipeline.run_turn(
            audio, session_id=session.id, conversation=session.conversation
        )
        await self._send(Frame("transcript", metadata={"text": result.transcript}))
        await self._send(Frame("reply", metadata={"text": result.reply}))
        if result.speech:
            await self._send(Frame("audio", payload=result.speech))

    async def _send(self, frame: Frame) -> None:
        for item in self.adapter.encode(frame):
            if isinstance(item, str):
                await self.ws.send_text(item)
            else:
                await self.ws.send_binary(item)

    async def close(self) -> None:
        if hasattr(self.ws, "close"):
            await self.ws.close()


class EngineRuntime:
    """组合会话与服务，一键提供真实服务。"""

    def __init__(self, pipeline_factory: Callable[[], AiPipeline]) -> None:
        self.registry = SessionRegistry()
        self.pipeline_factory = pipeline_factory

    async def serve(
        self, host: str = "127.0.0.1", port: int = 8765
    ) -> WebSocketServer:
        def handler(ws) -> None:
            return LegacySessionChannel(
                ws, self.pipeline_factory(), self.registry
            ).run()

        server = WebSocketServer(handler, host=host, port=port)
        await server.start()
        return server
