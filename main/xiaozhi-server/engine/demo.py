"""无外部依赖的端到端演示。

用法:
    python -m engine.demo --config engine/examples/demo.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .config import load_config, validate_config
from .contracts import AudioChunk
from .observers import EventBus, LoggingObserver, MetricsCollector
from .pipeline import AiPipeline
from .session import Conversation
from .session import SessionRegistry
from .stubs import register_standard_providers
from .transport import Frame, InMemoryTransport, JsonFrameCodec, RealtimeServer


def build_pipeline(config_path: str) -> AiPipeline:
    config = load_config(config_path)
    registry = register_standard_providers()
    errors = validate_config(config, registry)
    if errors:
        raise ValueError("\n".join(errors))

    asr = registry.create("asr", config.asr.name, options=config.asr.options)
    llm = registry.create("llm", config.llm.name, options=config.llm.options)
    tts = registry.create("tts", config.tts.name, options=config.tts.options)
    vad = (
        registry.create("vad", config.vad.name, options=config.vad.options)
        if config.vad
        else None
    )
    fallback = (
        registry.create(
            "llm", config.fallback_llm, options=config.llm.options
        )
        if config.fallback_llm
        else None
    )

    bus = EventBus()
    metrics_collector = MetricsCollector()
    bus.subscribe(LoggingObserver())
    bus.subscribe(metrics_collector)
    return AiPipeline(
        asr,
        llm,
        tts,
        vad,
        events=bus,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        fallback_llm=fallback,
    )


async def _run(config_path: str) -> None:
    pipeline = build_pipeline(config_path)
    conversation = Conversation(system_prompt="你是一个友好的助手。")
    audio = AudioChunk(pcm=b"\x00" * 3200, sample_rate=16000)
    for turn in range(1, 3):
        result = await pipeline.run_turn(audio, session_id="demo", conversation=conversation)
        print(f"=== 第 {turn} 轮 ===")
        print("转录:", result.transcript)
        print("回复:", result.reply)
        print("音频字节数:", len(result.speech))
        print("阶段耗时(s):", json.dumps(result.metrics, ensure_ascii=False))
    print("=== 会话历史条数 ===")
    print(len(conversation.messages))

    await _demo_transport(pipeline)


async def _transport_scene(pipeline: AiPipeline) -> list[str]:
    transport = InMemoryTransport()
    codec = JsonFrameCodec()
    server = RealtimeServer(SessionRegistry(), lambda: pipeline, codec)
    task = asyncio.create_task(server.handle_connection(transport))
    transport.push_raw(codec.encode(Frame("hello", metadata={"device_id": "dev-1"})))
    transport.push_raw(
        codec.encode(Frame("audio", b"\x00" * 320, {"sample_rate": 16000}))
    )
    transport.push_raw(codec.encode(Frame("bye")))
    await asyncio.wait_for(task, timeout=5)
    return [codec.decode(raw).type for raw in transport.outgoing]


async def _demo_transport(pipeline: AiPipeline) -> None:
    frame_types = await _transport_scene(pipeline)
    print("=== 实时通道帧序列 ===")
    print(" -> ".join(frame_types))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="engine 演示")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "examples" / "demo.json"),
        help="引擎 JSON 配置路径",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.config))


if __name__ == "__main__":
    main()
