"""能力契约与领域模型。

所有能力都通过这里定义的轻量接口与上层层交互：
- SpeechToText            语音转文本
- LanguageModel           大模型流式回复
- TextToSpeech            文本转语音
- VoiceActivityDetector   语音活动检测

实现方只依赖标准库与 Py3.10+ 类型标注，不绑定任何厂商 SDK。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Protocol, runtime_checkable


class PipelineStage(str, Enum):
    """编排状态机的阶段名称。"""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class AudioChunk:
    """一帧输入音频。"""

    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1


@dataclass(frozen=True)
class Transcript:
    """语音识别结果。"""

    text: str
    language: str = "zh"
    confidence: float = 1.0
    is_final: bool = True


@dataclass(frozen=True)
class Message:
    """对话消息。"""

    role: str
    content: str


@dataclass(frozen=True)
class ReplyChunk:
    """大模型回复片段。"""

    text: str
    is_final: bool = False


@dataclass(frozen=True)
class SpeechChunk:
    """合成语音片段。"""

    pcm: bytes
    sample_rate: int = 24000
    text: str = ""
    is_final: bool = False


@dataclass(frozen=True)
class TurnResult:
    """一次完整交互回合的结果。"""

    transcript: str
    reply: str
    speech: bytes = b""
    events: list[PipelineEvent] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class SpeechToText(Protocol):
    async def transcribe(self, audio: AudioChunk, session_id: str) -> Transcript: ...


@runtime_checkable
class LanguageModel(Protocol):
    def stream_reply(
        self, messages: list[Message], session_id: str
    ) -> AsyncIterator[ReplyChunk]: ...


@runtime_checkable
class TextToSpeech(Protocol):
    def synthesize(self, text: str, session_id: str) -> AsyncIterator[SpeechChunk]: ...


@runtime_checkable
class VoiceActivityDetector(Protocol):
    def is_speech(self, audio: AudioChunk) -> bool: ...
