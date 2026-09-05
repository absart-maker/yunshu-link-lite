"""AI 引擎层：原创可插拔能力编排核心。

本包与第三方模型 SDK 解耦，定义能力契约、Provider 注册体系、配置校验
以及异步编排状态机，并通过 bridge 兼容现有 Provider 实现。
"""

from .config import EngineConfig, ProviderConfig, load_config, validate_config
from .contracts import (
    AudioChunk,
    Message,
    PipelineStage,
    ReplyChunk,
    SpeechChunk,
    Transcript,
    TurnResult,
)
from .observers import EventBus, LoggingObserver, MetricsCollector, PipelineEvent
from .pipeline import AiPipeline, PipelineError
from .registry import ProviderRegistry, ProviderSpec
from .session import Conversation, Session, SessionRegistry
from .transport import (
    AsyncTransport,
    Frame,
    FrameCodec,
    InMemoryTransport,
    JsonFrameCodec,
    RealtimeDeviceChannel,
    RealtimeServer,
)
from .device_simulator import DeviceSimulator, LoopbackTransport
from .ws import WebSocketConnection, WebSocketServer
from .integration import (
    EngineRuntime,
    LegacyProtocolAdapter,
    LegacySessionChannel,
    build_pipeline_from_config,
)

__version__ = "1.0.0"

__all__ = [
    "AiPipeline",
    "AsyncTransport",
    "AudioChunk",
    "Conversation",
    "DeviceSimulator",
    "EngineRuntime",
    "EngineConfig",
    "EventBus",
    "Frame",
    "FrameCodec",
    "InMemoryTransport",
    "JsonFrameCodec",
    "LegacyProtocolAdapter",
    "LegacySessionChannel",
    "LoopbackTransport",
    "LoggingObserver",
    "Message",
    "MetricsCollector",
    "PipelineError",
    "PipelineEvent",
    "PipelineStage",
    "ProviderConfig",
    "ProviderRegistry",
    "ProviderSpec",
    "RealtimeDeviceChannel",
    "RealtimeServer",
    "ReplyChunk",
    "Session",
    "SessionRegistry",
    "SpeechChunk",
    "Transcript",
    "TurnResult",
    "WebSocketConnection",
    "WebSocketServer",
    "build_pipeline_from_config",
    "load_config",
    "validate_config",
]
