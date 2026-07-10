from typing import Any, Callable, Optional


_fallback_registry: dict[str, Callable[..., Any]] = {}


def register_fallback(name: str, fn: Callable[..., Any]) -> None:
    _fallback_registry[name] = fn


def get_fallback(name: str) -> Optional[Callable[..., Any]]:
    return _fallback_registry.get(name)


def has_fallback(name: str) -> bool:
    return name in _fallback_registry
