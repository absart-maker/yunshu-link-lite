"""大模型桥接适配。"""

from __future__ import annotations

from typing import AsyncIterator

from ..contracts import Message, ReplyChunk


class LegacyLanguageModel:
    """把旧式 LLMProviderBase.response 生成器包装成新契约。"""

    def __init__(self, provider) -> None:
        self._provider = provider

    def stream_reply(
        self, messages: list[Message], session_id: str
    ) -> AsyncIterator[ReplyChunk]:
        dialogue = [{"role": m.role, "content": m.content} for m in messages]

        async def generate() -> AsyncIterator[ReplyChunk]:
            for token in self._provider.response(session_id, dialogue):
                yield ReplyChunk(text=str(token), is_final=False)

        return generate()
