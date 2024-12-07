from __future__ import annotations

from copy import copy
from functools import wraps
from typing import TYPE_CHECKING, Concatenate, ParamSpec, Self, TypeVar

from yarl import URL

if TYPE_CHECKING:
    from collections.abc import Callable

M = TypeVar("M", bound="MarkdownBuilder")
P = ParamSpec("P")
StrOrUrl = TypeVar("StrOrUrl", str, URL)

__all__ = ("MarkdownBuilder",)


def clamp(value: int, /, max_: int, min_: int) -> int:
    return min(max(min_, value), max_)


def after_markdown(func: Callable[Concatenate[M, P], M]) -> Callable[Concatenate[M, P], M]:
    @wraps(func)
    def wrapper(item: M, *args: P.args, **kwargs: P.kwargs) -> M:
        func(item, *args, **kwargs)
        item._inner += "\n"

        return item

    return wrapper


class MarkdownBuilder:
    def __init__(self) -> None:
        self._inner: str = ""

    def __str__(self) -> str:
        return self.text

    @property
    def text(self) -> str:
        return self._inner

    @text.getter
    def text(self) -> str:
        c = copy(self._inner)
        self.clear()
        return c

    @after_markdown
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

    @after_markdown
    def add_link(self, *, url: StrOrUrl, text: str) -> Self:
        self._inner += f"[{text}]({url})"

        return self

    @after_markdown
    def add_bulletpoints(self, *, texts: list[str]) -> Self:
        builder = ""
        for item in texts:
            builder += f" - {item}\n"

        self._inner += builder

        return self

    @after_markdown
    def add_text(self, *, text: str) -> Self:
        self._inner += text

        return self

    @after_markdown
    def add_newline(self, *, amount: int = 1) -> Self:
        self._inner += "\n" * amount

        return self

    def clear(self) -> None:
        self._inner = ""
