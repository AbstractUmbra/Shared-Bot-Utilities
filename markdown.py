from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, Self, TypeVar

from yarl import URL

if TYPE_CHECKING:
    from collections.abc import Callable

M = TypeVar("M", bound="MarkdownBuilder")
P = ParamSpec("P")
T = TypeVar("T")
StrOrUrl = TypeVar("StrOrUrl", str, URL)

__all__ = ("MarkdownBuilder",)


def clamp(value: int, /, max_: int, min_: int) -> int:
    return min(max(min_, value), max_)


class AfterCallMeta(type):
    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> AfterCallMeta:
        for key, val in attrs.items():
            if callable(val) and not key.startswith("__"):
                original = val

                def make_wrapper(func: Callable[Concatenate[M, P], T]) -> Callable[Concatenate[M, P], T]:
                    def wrapper(self: M, *args: P.args, **kwargs: P.kwargs) -> T:
                        result = func(self, *args, **kwargs)
                        if self._skip is True:
                            self._skip = False
                            return result

                        self._after_method()
                        return result

                    return wrapper

                attrs[key] = make_wrapper(original)
        return super().__new__(cls, name, bases, attrs)


class MarkdownBuilder(metaclass=AfterCallMeta):
    def __init__(self) -> None:
        self._inner: str = ""
        self._skip: bool = False

    def __str__(self) -> str:
        return self.text

    def _after_method(self) -> None:
        self._inner += "\n"

    @property
    def text(self) -> str:
        self._skip = True
        return self._inner

    @text.getter
    def text(self) -> str:
        self._skip = True
        c = copy(self._inner)
        self.clear()
        return c

    def add_header(self, *, text: str, depth: int = 1) -> Self:
        depth = clamp(depth, 5, 1)
        self._inner += "#" * depth
        self._inner += " " + text

        return self

    def add_subtitle(self, text: str, /) -> Self:
        lines = self._inner.split("\n")
        lines.insert(-1, f"-# {text}")
        self._inner = "\n".join(lines)

        return self

    def add_link(self, *, url: StrOrUrl, text: str) -> Self:
        self._inner += f"[{text}]({url})"

        return self

    def add_bulletpoints(self, *, texts: list[str]) -> Self:
        builder = ""
        for item in texts:
            builder += f" - {item}\n"

        self._inner += builder

        return self

    def add_text(self, *, text: str) -> Self:
        self._inner += text

        return self

    def add_newline(self, *, amount: int = 1) -> Self:
        self._skip = True

        self._inner += "\n" * amount

        return self

    def clear(self) -> None:
        self._skip = True
        self._inner = ""
