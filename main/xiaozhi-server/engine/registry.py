"""Provider 注册体系。

以「能力分类 + 实现名」二维定位 Provider，提供注册、查询、实例化与
配置校验，让上层无需关心具体实现细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Tuple


Factory = Callable[..., Any]


@dataclass(frozen=True)
class ProviderSpec:
    """一个 Provider 的元信息。"""

    name: str
    category: str
    factory: Factory
    required_config: Tuple[str, ...] = ()
    description: str = ""


class ProviderNotFoundError(KeyError):
    pass


class ProviderRegistry:
    """线程无关的注册表，支持装饰器注册与配置驱动创建。"""

    def __init__(self) -> None:
        self._specs: Dict[str, Dict[str, ProviderSpec]] = {}

    def register(
        self,
        name: str,
        category: str,
        factory: Factory,
        required_config: Iterable[str] = (),
        description: str = "",
    ) -> None:
        if not name or not category:
            raise ValueError("name 与 category 不能为空")
        if not callable(factory):
            raise TypeError("factory 必须是可调用对象")
        spec = ProviderSpec(
            name=name,
            category=category,
            factory=factory,
            required_config=tuple(required_config),
            description=description,
        )
        self._specs.setdefault(category, {})[name] = spec

    def register_provider(
        self,
        category: str,
        name: str,
        *,
        required_config: Iterable[str] = (),
        description: str = "",
    ) -> Callable[[Factory], Factory]:
        def decorator(factory: Factory) -> Factory:
            self.register(name, category, factory, required_config, description)
            return factory

        return decorator

    def get(self, category: str, name: str) -> ProviderSpec:
        try:
            return self._specs[category][name]
        except KeyError as exc:
            known = ", ".join(self.names(category)) or "无"
            raise ProviderNotFoundError(
                f"Provider 不存在: {category}.{name}；当前可用的同分类实现: {known}"
            ) from exc

    def has(self, category: str, name: str) -> bool:
        return name in self._specs.get(category, {})

    def names(self, category: str) -> list[str]:
        return sorted(self._specs.get(category, {}))

    def categories(self) -> list[str]:
        return sorted(self._specs)

    def validate_options(
        self, category: str, name: str, options: dict[str, Any]
    ) -> list[str]:
        spec = self.get(category, name)
        missing = [key for key in spec.required_config if key not in options]
        if missing:
            return [f"{category}.{name} 缺少必填配置: {', '.join(missing)}"]
        return []

    def create(
        self, category: str, name: str, *, options: dict[str, Any] | None = None
    ) -> Any:
        options = options or {}
        errors = self.validate_options(category, name, options)
        if errors:
            raise ValueError("; ".join(errors))
        spec = self.get(category, name)
        return spec.factory(**options)

    def __len__(self) -> int:
        return sum(len(items) for items in self._specs.values())
