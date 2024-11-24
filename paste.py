from __future__ import annotations

from typing import TYPE_CHECKING

import mystbin

if TYPE_CHECKING:
    import datetime


async def create_paste(
    *,
    content: str,
    password: str | None = None,
    expiry: datetime.datetime | None = None,
    mb_client: mystbin.Client,
) -> str:
    paste = await mb_client.create_paste(
        files=[mystbin.File(filename="output.py", content=content)],
        expires=expiry,
        password=password,
    )

    return paste.url
