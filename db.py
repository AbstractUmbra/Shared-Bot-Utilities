"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Code below is sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .formats import from_json, to_json

if TYPE_CHECKING:
    import asyncpg

__all__ = (
    "MaybeAcquire",
    "db_init",
)


class MaybeAcquire:
    __slots__ = (
        "_cleanup",
        "_connection",
        "pool",
    )

    def __init__(self, connection: asyncpg.Connection[asyncpg.Record] | None, *, pool: asyncpg.Pool[asyncpg.Record]) -> None:
        self.pool: asyncpg.Pool[asyncpg.Record] = pool
        self._connection: asyncpg.Connection[asyncpg.Record] | None = connection
        self._cleanup: bool = False

    async def __aenter__(self) -> asyncpg.Connection[asyncpg.Record]:
        if self._connection is None:
            self._cleanup = True
            self._connection = await self.pool.acquire()  # pyright: ignore[reportAttributeAccessIssue] # navigating stubs
        return self._connection  # pyright: ignore[reportReturnType] # navigating stubs

    async def __aexit__(self, *args: object) -> None:
        if self._cleanup:
            await self.pool.release(self._connection)  # pyright: ignore[reportArgumentType] # navigating stubs


def _encode_jsonb(value: Any) -> str:
    return to_json(value)


def _decode_jsonb(value: str) -> Any:
    return from_json(value)


async def db_init(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=_encode_jsonb, decoder=_decode_jsonb)
