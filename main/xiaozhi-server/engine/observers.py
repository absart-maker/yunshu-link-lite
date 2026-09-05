"""事件总线与可观测性组件。

编排器只负责产生事件，具体观察者通过 EventBus 订阅，做到核心逻辑与
日志、指标、审计解耦。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .contracts import PipelineStage


@dataclass(frozen=True)
class PipelineEvent:
    name: str
    stage: PipelineStage
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


Listener = Callable[[PipelineEvent], None]


class EventBus:
    """简单的同步事件分发器。"""

    ANY = "*"

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Listener]] = {}

    def subscribe(self, listener: Listener, event_name: str = ANY) -> None:
        self._listeners.setdefault(event_name, []).append(listener)

    def unsubscribe(self, listener: Listener, event_name: str = ANY) -> None:
        self._listeners.get(event_name, []).remove(listener)

    def publish(self, event: PipelineEvent) -> None:
        for listener in list(self._listeners.get(self.ANY, ())):
            listener(event)
        for listener in list(self._listeners.get(event.name, ())):
            listener(event)

    def __len__(self) -> int:
        return sum(len(items) for items in self._listeners.values())


class LoggingObserver:
    """把事件写入结构化日志。"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("engine.events")

    def __call__(self, event: PipelineEvent) -> None:
        self._logger.info(
            "stage=%s event=%s payload=%s",
            event.stage.value,
            event.name,
            event.payload,
        )


class MetricsCollector:
    """按事件统计次数与阶段耗时。"""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}
        self._markers: Dict[str, float] = {}
        self._durations: Dict[str, float] = {}

    def _stage_start(self, stage: PipelineStage) -> None:
        self._markers[stage.value] = time.monotonic()

    def _stage_end(self, stage: PipelineStage) -> None:
        start = self._markers.pop(stage.value, None)
        if start is not None:
            self._durations[stage.value] = time.monotonic() - start

    def __call__(self, event: PipelineEvent) -> None:
        self._counts[event.name] = self._counts.get(event.name, 0) + 1
        if event.name == "stage.enter":
            self._stage_start(event.stage)
        elif event.name == "stage.exit":
            self._stage_end(event.stage)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(self._counts),
            "durations": dict(self._durations),
        }
