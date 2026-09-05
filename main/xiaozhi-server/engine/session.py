"""会话层：多轮对话状态与生命周期管理。

本模块不关心音频/网络，只维护「一次设备连接内的对话上下文」，
为编排状态机提供历史消息、元信息与并发安全的数据容器。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .contracts import Message


@dataclass
class Conversation:
    """对话历史，带系统提示与上限。"""

    system_prompt: str = ""
    max_messages: int = 40
    messages: list[Message] = field(default_factory=list)

    def reset(self) -> None:
        self.messages.clear()

    def append(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        if len(self.messages) > self.max_messages:
            # 保留系统提示与最近 max_messages 条
            overflow = len(self.messages) - self.max_messages
            del self.messages[:overflow]

    def snapshot(self) -> list[Message]:
        head: list[Message] = []
        if self.system_prompt:
            head.append(Message(role="system", content=self.system_prompt))
        return head + list(self.messages)

    def estimated_tokens(self) -> int:
        """粗略估算 token 数（中文约 1.5 字/token，英文约 4 字符/token）。"""

        total = 0
        for message in self.messages + ([Message("system", self.system_prompt)] if self.system_prompt else []):
            for char in message.content:
                total += 1 if ord(char) > 127 else 0
            total += len(message.content.encode("utf-8")) - sum(
                1 if ord(ch) > 127 else 0 for ch in message.content
            )
        return total


@dataclass
class Session:
    """一次设备连接对应的会话。"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    device_id: str = ""
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)
    conversation: Conversation = field(default_factory=Conversation)
    metadata: dict[str, object] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_active = time.monotonic()


class SessionRegistry:
    """线程安全的会话注册表，支持数量上限与空闲回收。"""

    def __init__(self, max_sessions: int = 1000, idle_timeout: float = 3600.0) -> None:
        self.max_sessions = max_sessions
        self.idle_timeout = idle_timeout
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def create(self, device_id: str = "", **metadata: object) -> Session:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                self.evict_idle()
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError("会话数量已达上限")
            session = Session(device_id=device_id, metadata=metadata)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.touch()
            return session

    def close(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def evict_idle(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [
                key
                for key, session in self._sessions.items()
                if now - session.last_active > self.idle_timeout
            ]
            for key in expired:
                self._sessions.pop(key, None)
            return len(expired)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
