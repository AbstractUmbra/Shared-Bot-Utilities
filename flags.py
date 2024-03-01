"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

from __future__ import annotations

from functools import reduce
from typing import TYPE_CHECKING, Any, Self, TypeVar, overload

from discord.flags import BaseFlags as DpyFlags, fill_with_flags

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Self

__all__ = (
    "BaseFlags",
    "flag_value",
    "SubscribedEventsFlags",
)

T = TypeVar("T", bound="BaseFlags")


class BaseFlags:
    __slots__ = ("value",)

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} value={self.value}>"

    def is_empty(self) -> bool:
        """Returns true if the flags are empty (i.e. a zero value)"""
        return self.value == 0

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) == o

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value |= o
        elif toggle is False:
            self.value &= ~o
        else:
            raise TypeError(f"Value to set for {self.__class__.__name__} must be a bool.")


class flag_value:
    def __init__(self, func: Callable[[Any], int]) -> None:
        self.flag: int = func(None)
        self.__doc__: str | None = func.__doc__

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> Self:
        ...

    @overload
    def __get__(self, instance: T, owner: type[T]) -> bool:
        ...

    def __get__(self, instance: T | None, owner: type[T]) -> Any:
        if instance is None:
            return self
        return instance._has_flag(self.flag)

    def __set__(self, instance: BaseFlags, value: bool) -> None:
        instance._set_flag(self.flag, value)

    def __repr__(self) -> str:
        return f"<flag_value flag={self.flag!r}>"


@fill_with_flags()
class SubscribedEventsFlags(DpyFlags):
    __slots__ = ()

    def __init__(self, value: int = 0, **kwargs: bool) -> None:
        self.value: int = value
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f"{key!r} is not a valid flag name.")
            setattr(self, key, value)

    @classmethod
    def all(cls: type[Self]) -> Self:
        value = reduce(lambda a, b: a | b, cls.VALID_FLAGS.values())
        self = cls.__new__(cls)
        self.value = value
        return self

    @classmethod
    def none(cls: type[Self]) -> Self:
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @flag_value
    def daily_resets(self) -> int:
        return 1 << 0

    @flag_value
    def weekly_resets(self) -> int:
        return 1 << 1

    @flag_value
    def fashion_report(self) -> int:
        return 1 << 2

    @flag_value
    def ocean_fishing(self) -> int:
        return 1 << 3

    @flag_value
    def jumbo_cactpot_na(self) -> int:
        return 1 << 4

    @flag_value
    def jumbo_cactpot_eu(self) -> int:
        return 1 << 5

    @flag_value
    def jumbo_cactpot_jp(self) -> int:
        return 1 << 6

    @flag_value
    def jumbo_cactpot_oce(self) -> int:
        return 1 << 7

    @flag_value
    def gate(self) -> int:
        return 1 << 8
