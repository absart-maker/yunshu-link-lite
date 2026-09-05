"""语音合成桥接适配。"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from ..contracts import SpeechChunk


class LegacyTextToSpeech:
    """把旧式 `to_tts(text) -> bytes` 同步方法包装成异步契约。"""

    def __init__(self, provider, sample_rate: int = 24000) -> None:
        self._provider = provider
        self._sample_rate = sample_rate

    def synthesize(
        self, text: str, session_id: str
    ) -> AsyncIterator[SpeechChunk]:
        async def generate() -> AsyncIterator[SpeechChunk]:
            pcm = await asyncio.to_thread(self._provider.to_tts, text)
            yield SpeechChunk(
                pcm=bytes(pcm or b""),
                sample_rate=self._sample_rate,
                text=text,
                is_final=True,
            )

        return generate()


class StreamingTextToSpeech:
    """适配旧式 `to_tts_stream(text, opus_handler)` 流式回调。"""

    def __init__(self, provider, sample_rate: int = 24000) -> None:
        self._provider = provider
        self._sample_rate = sample_rate

    def synthesize(
        self, text: str, session_id: str
    ) -> AsyncIterator[SpeechChunk]:
        async def generate() -> AsyncIterator[SpeechChunk]:
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            def on_chunk(data: bytes) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, data)

            def run_sync() -> None:
                try:
                    self._provider.to_tts_stream(text, on_chunk)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            task = asyncio.create_task(asyncio.to_thread(run_sync))
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield SpeechChunk(
                    pcm=chunk,
                    sample_rate=self._sample_rate,
                    text=text,
                    is_final=False,
                )
            await task

        return generate()
