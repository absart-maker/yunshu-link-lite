"""异步编排状态机。

一个 Turn 的生命周期：

  idle -> listening -> transcribing -> thinking -> speaking -> done
                              |                            |
                              +----(vad 拒绝/异常)-------> failed

编排器只控制流程与超时/重试/降级，具体能力由注入对象提供。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from .contracts import (
    AudioChunk,
    LanguageModel,
    Message,
    PipelineStage,
    ReplyChunk,
    SpeechChunk,
    SpeechToText,
    TextToSpeech,
    Transcript,
    TurnResult,
    VoiceActivityDetector,
)
from .observers import EventBus, PipelineEvent
from .session import Conversation


class PipelineError(RuntimeError):
    """编排失败时抛出。"""


@dataclass
class TurnMetrics:
    per_stage: dict[str, float]


class AiPipeline:
    """一次语音交互回合的编排器。"""

    def __init__(
        self,
        asr: SpeechToText,
        llm: LanguageModel,
        tts: TextToSpeech,
        vad: VoiceActivityDetector | None = None,
        *,
        events: EventBus | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        fallback_llm: LanguageModel | None = None,
    ) -> None:
        self.asr = asr
        self.llm = llm
        self.tts = tts
        self.vad = vad
        self.events = events or EventBus()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.fallback_llm = fallback_llm

    def emit(self, name: str, stage: PipelineStage, **payload: object) -> PipelineEvent:
        event = PipelineEvent(name=name, stage=stage, payload=payload)
        self.events.publish(event)
        self._turn_events.append(event)
        return event

    async def run_turn(
        self,
        audio: AudioChunk,
        session_id: str,
        conversation: Optional[Conversation] = None,
    ) -> TurnResult:
        metrics: dict[str, float] = {}

        try:
            self._clear()
            self.emit("turn.start", PipelineStage.IDLE, session_id=session_id)
            self._enter(PipelineStage.LISTENING)

            if self.vad is not None and not self.vad.is_speech(audio):
                self._exit(PipelineStage.LISTENING, metrics)
                self.emit(
                    "voice.rejected",
                    PipelineStage.DONE,
                    reason="no_speech",
                    session_id=session_id,
                )
                return TurnResult("", "", b"", list(self._turn_events), metrics)

            self._exit(PipelineStage.LISTENING, metrics)
            self._enter(PipelineStage.TRANSCRIBING)
            transcript = await self._with_timeout(
                self.asr.transcribe(audio, session_id), "asr", metrics
            )
            self._exit(PipelineStage.TRANSCRIBING, metrics)
            self.emit("asr.done", PipelineStage.TRANSCRIBING, text=transcript.text)

            self._enter(PipelineStage.THINKING)
            history = list(conversation.snapshot()) if conversation is not None else []
            messages = history + [Message(role="user", content=transcript.text)]
            reply = await self._reply(messages, session_id, metrics)
            self._exit(PipelineStage.THINKING, metrics)
            self.emit("llm.done", PipelineStage.THINKING, text=reply)

            if conversation is not None:
                conversation.append("user", transcript.text)
                conversation.append("assistant", reply)

            self._enter(PipelineStage.SPEAKING)
            speech = await self._synthesize(reply, session_id, metrics)
            self._exit(PipelineStage.SPEAKING, metrics)
            self.emit("tts.done", PipelineStage.SPEAKING, bytes=len(speech))

            self.emit("turn.done", PipelineStage.DONE, session_id=session_id)
            return TurnResult(
                transcript.text, reply, speech, list(self._turn_events), metrics
            )
        except Exception as exc:
            self.emit(
                "turn.failed",
                PipelineStage.FAILED,
                error=type(exc).__name__,
                session_id=session_id,
            )
            raise PipelineError(f"turn 执行失败: {exc}") from exc

    async def _with_timeout(
        self,
        awaitable,
        name: str,
        metrics: dict[str, float],
    ) -> Transcript:
        start = time.monotonic()
        try:
            return await asyncio.wait_for(awaitable, timeout=self.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise PipelineError(f"{name} 超时({self.timeout_seconds}s)") from exc
        finally:
            metrics[name] = time.monotonic() - start

    async def _reply(
        self,
        messages: list[Message],
        session_id: str,
        metrics: dict[str, float],
    ) -> str:
        candidates: list[LanguageModel] = [self.llm]
        if self.fallback_llm is not None and self.fallback_llm is not self.llm:
            candidates.append(self.fallback_llm)
        last_error: Optional[BaseException] = None
        for index, model in enumerate(candidates[: self.max_retries + 1]):
            try:
                return await asyncio.wait_for(
                    self._collect_reply(model, messages, session_id, metrics),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                self.emit(
                    "llm.retry",
                    PipelineStage.THINKING,
                    attempt=index + 1,
                    error=type(exc).__name__,
                )
        raise PipelineError(f"LLM 全部尝试失败: {last_error}")

    async def _collect_reply(
        self,
        model: LanguageModel,
        messages: list[Message],
        session_id: str,
        metrics: dict[str, float],
    ) -> str:
        start = time.monotonic()
        parts: list[str] = []
        iterator: AsyncIterator[ReplyChunk] = model.stream_reply(messages, session_id)
        async for chunk in iterator:
            parts.append(chunk.text)
        metrics["llm"] = time.monotonic() - start
        return "".join(parts)

    async def _synthesize(
        self, text: str, session_id: str, metrics: dict[str, float]
    ) -> bytes:
        start = time.monotonic()
        chunks: list[bytes] = []
        iterator: AsyncIterator[SpeechChunk] = self.tts.synthesize(text, session_id)
        async for chunk in iterator:
            chunks.append(chunk.pcm)
            self.emit(
                "tts.chunk",
                PipelineStage.SPEAKING,
                bytes=len(chunk.pcm),
                text=chunk.text,
            )
        metrics["tts"] = time.monotonic() - start
        return b"".join(chunks)

    def _clear(self) -> None:
        self._stage_stack: list[PipelineStage] = []
        self._turn_events: list[PipelineEvent] = []

    def _enter(self, stage: PipelineStage) -> None:
        self._stage_stack.append(stage)
        self.emit("stage.enter", stage)

    def _exit(self, stage: PipelineStage, metrics: dict[str, float]) -> None:
        if self._stage_stack:
            self._stage_stack.pop()
        self.emit("stage.exit", stage)
