"""引擎配置模型。

配置以 JSON 描述，结构简单、可版本化、便于给上层做配置文件映射。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

from .registry import ProviderRegistry


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineConfig:
    asr: ProviderConfig
    llm: ProviderConfig
    tts: ProviderConfig
    vad: ProviderConfig | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 1
    fallback_llm: str | None = None


def _provider_from_dict(key: str, data: dict[str, Any]) -> ProviderConfig:
    item = data.get(key)
    if not isinstance(item, dict) or not item.get("name"):
        raise ValueError(f"配置缺少 {key}.name")
    return ProviderConfig(name=str(item["name"]), options=dict(item.get("options", {})))


def config_from_dict(data: dict[str, Any]) -> EngineConfig:
    engine = data.get("engine", data)
    return EngineConfig(
        asr=_provider_from_dict("asr", engine),
        llm=_provider_from_dict("llm", engine),
        tts=_provider_from_dict("tts", engine),
        vad=(
            _provider_from_dict("vad", engine)
            if "vad" in engine and engine.get("vad")
            else None
        ),
        timeout_seconds=float(engine.get("timeout_seconds", 30.0)),
        max_retries=int(engine.get("max_retries", 1)),
        fallback_llm=engine.get("fallback_llm"),
    )


def load_config(path: str | Path) -> EngineConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return config_from_dict(raw)


def validate_config(config: EngineConfig, registry: ProviderRegistry) -> List[str]:
    errors: List[str] = []
    for key, provider in (
        ("asr", config.asr),
        ("llm", config.llm),
        ("tts", config.tts),
    ):
        if not registry.has(key, provider.name):
            errors.append(f"未注册的 {key}.{provider.name}")
            continue
        errors.extend(registry.validate_options(key, provider.name, provider.options))
    if config.vad is not None and not registry.has("vad", config.vad.name):
        errors.append(f"未注册的 vad.{config.vad.name}")
    return errors
