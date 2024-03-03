"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload

from .formats import from_json, to_json

if TYPE_CHECKING:
    import pathlib

    from typing_extensions import TypeVar  # noqa: TCH004

    _T = TypeVar("_T", default=Any)
else:
    _T = TypeVar("_T")
_defT = TypeVar("_defT")


class Config(Generic[_T]):
    """The "database" object. Internally based on ``json``."""

    def __init__(
        self,
        path: pathlib.Path,
        /,
        *,
        load_later: bool = False,
    ) -> None:
        self.path = path
        self.loop = asyncio.get_event_loop()
        self.lock = asyncio.Lock()
        self._db: dict[str, _T] = {}

        if load_later:
            self.loop.create_task(self.load())
        else:
            self.load_from_file()

    def load_from_file(self) -> None:
        try:
            with self.path.open() as f:
                self._db = from_json(f.read())
        except FileNotFoundError:
            self._db = {}

    async def load(self) -> None:
        async with self.lock:
            await self.loop.run_in_executor(None, self.load_from_file)

    def _dump(self) -> None:
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as tmp:
            tmp.write(to_json(self._db.copy()))

        # atomically move the file
        temp.replace(self.path)

    async def save(self) -> None:
        async with self.lock:
            await self.loop.run_in_executor(None, self._dump)

    @overload
    def get(self, key: Any) -> _T | None: ...

    @overload
    def get(self, key: Any, default: _defT) -> _T | _defT: ...

    def get(self, key: Any, default: _defT = None) -> _T | _defT | None:
        """Retrieves a config entry."""
        return self._db.get(str(key), default)

    async def put(self, key: Any, value: _T) -> None:
        """Edits a config entry."""
        self._db[str(key)] = value
        await self.save()

    __setitem__ = put

    async def remove(self, key: Any) -> None:
        """Removes a config entry."""
        try:
            del self._db[str(key)]
        except KeyError:
            return
        await self.save()

    def __contains__(self, item: Any) -> bool:
        return str(item) in self._db

    def __getitem__(self, item: Any) -> _T:
        return self._db[str(item)]

    def __len__(self) -> int:
        return len(self._db)

    def all(self) -> dict[str, _T]:
        return self._db
