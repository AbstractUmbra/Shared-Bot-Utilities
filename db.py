"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

__all__ = ("MaybeAcquire", "db_init")


class MaybeAcquire:
    def __init__(
        self,
        connection: asyncpg.Connection[asyncpg.Record] | None,
        *,
        pool: asyncpg.Pool[asyncpg.Record],
    ) -> None:
        self.connection: asyncpg.Connection[asyncpg.Record] | None = connection
        self.pool: asyncpg.Pool[asyncpg.Record] = pool
        self._cleanup: bool = False

    async def __aenter__(self) -> asyncpg.Connection[asyncpg.Record]:
        if self.connection is None:
            self._cleanup = True
            self.connection = await self.pool.acquire()
        return self.connection

    async def __aexit__(self, *args: Any) -> None:
        if self._cleanup:
            await self.pool.release(self.connection)


def _encode_jsonb(value: Any) -> str:
    return json.dumps(value)


def _decode_jsonb(value: str) -> Any:
    return json.loads(value)


async def db_init(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec(
        "jsonb", schema="pg_catalog", encoder=_encode_jsonb, decoder=_decode_jsonb
    )
