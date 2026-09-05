"""语音识别桥接适配。"""

from __future__ import annotations

from typing import Callable, Coroutine

from ..contracts import AudioChunk, Transcript


class FunctionSpeechToText:
    """把一个「音频字节 -> 文本」的同步/异步函数包装成契约。"""

    def __init__(
        self,
        transcribe: Callable[[bytes], str | Coroutine[None, None, str]],
        sample_rate: int = 16000,
    ) -> None:
        self._transcribe = transcribe
        self._sample_rate = sample_rate

    async def transcribe(self, audio: AudioChunk, session_id: str) -> Transcript:
        result = self._transcribe(audio.pcm)
        if hasattr(result, "__await__"):
            text = await result
        else:
            text = result
        return Transcript(text=str(text), confidence=1.0)


class LegacySpeechToText:
    """适配旧式 ASR Provider。

    旧实现需要 ConnectionHandler 才能缓冲音频与触发识别，因此这里按
    「握手回调」设计：接入方提供一个 `create_session(device_id)` 工厂，
    返回一个具备 `receive_audio(pcm)` 能力的连接代理。
    """

    def __init__(self, provider, connection_factory: Callable[[str], object]) -> None:
        self._provider = provider
        self._connection_factory = connection_factory
        self._connections: dict[str, object] = {}

    async def transcribe(self, audio: AudioChunk, session_id: str) -> Transcript:
        connection = self._connections.get(session_id)
        if connection is None:
            connection = self._connection_factory(session_id)
            self._connections[session_id] = connection
        await self._provider.receive_audio(connection, audio.pcm, True)
        text = getattr(connection, "last_text", "") or ""
        if not text:
            text = getattr(connection, "text", "") or ""
        return Transcript(text=str(text))
