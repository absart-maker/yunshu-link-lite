"""标准参考实现。

这些实现既不调用网络也不加载模型，用于：
1. 引擎层单元测试；
2. 无外部依赖的端到端演示；
3. 作为新 Provider 的书写范式。
"""

from __future__ import annotations

from typing import AsyncIterator

from .contracts import AudioChunk, Message, ReplyChunk, SpeechChunk, Transcript
from .registry import ProviderRegistry


class EchoASR:
    """把输入固定转成示范文本的识别器。"""

    async def transcribe(self, audio: AudioChunk, session_id: str) -> Transcript:
        return Transcript(text="请介绍一下这个引擎", confidence=0.99)


class RuleLLM:
    """按规则逐字输出回复。"""

    def __init__(self, reply: str = "这是一个可插拔的 AI 编排引擎。") -> None:
        self.reply = reply

    def stream_reply(
        self, messages: list[Message], session_id: str
    ) -> AsyncIterator[ReplyChunk]:
        async def generate() -> AsyncIterator[ReplyChunk]:
            for index, char in enumerate(self.reply):
                is_final = index == len(self.reply) - 1
                yield ReplyChunk(text=char, is_final=is_final)

        return generate()


class PaletteTTS:
    """把文本编码成静音 PCM 的合成器。"""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate

    def synthesize(
        self, text: str, session_id: str
    ) -> AsyncIterator[SpeechChunk]:
        payload = text.encode("utf-8")[:64]

        async def generate() -> AsyncIterator[SpeechChunk]:
            yield SpeechChunk(
                pcm=payload,
                sample_rate=self.sample_rate,
                text=text,
                is_final=True,
            )

        return generate()


class AlwaysVoiceVAD:
    def is_speech(self, audio: AudioChunk) -> bool:
        return True


class AlwaysSilenceVAD:
    def is_speech(self, audio: AudioChunk) -> bool:
        return False


class FailingLLM:
    """用于测试重试/降级链路。"""

    def __init__(self, message: str = "模拟故障") -> None:
        self.message = message

    def stream_reply(
        self, messages: list[Message], session_id: str
    ) -> AsyncIterator[ReplyChunk]:
        raise RuntimeError(self.message)


def register_standard_providers() -> ProviderRegistry:
    registry = ProviderRegistry()

    def _register(category: str, name: str, factory, description: str = "") -> None:
        registry.register(name, category, factory, description=description)

    _register("asr", "echo", EchoASR, "固定返回示例文本")
    _register("llm", "rule", RuleLLM, "规则逐字输出")
    _register("llm", "failing", FailingLLM, "用于演示故障与降级")
    _register("tts", "palette", PaletteTTS, "生成静音 PCM")
    _register("vad", "always_voice", AlwaysVoiceVAD, "始终判定为语音")
    _register("vad", "always_silence", AlwaysSilenceVAD, "始终判定为静音")
    return registry


DEFAULT_REGISTRY = register_standard_providers()
