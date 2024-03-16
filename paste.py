from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import datetime

    from aiohttp import ClientSession


async def create_paste(
    *,
    content: str,
    password: str | None = None,
    expiry: datetime.datetime | None = None,
    language: str = "py",
    session: ClientSession,
) -> str:
    async with session.post(
        "https://paste.abstractumbra.dev/data/post", data=content, headers={"Content-Type": f"text/{language}"}
    ) as resp:
        data = await resp.json()
        paste_key = data["key"]

        return f"https://paste.abstractumbra.dev/{paste_key}"
