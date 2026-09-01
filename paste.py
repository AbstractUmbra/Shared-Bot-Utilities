from __future__ import annotations

import datetime
import secrets
from typing import TYPE_CHECKING, NamedTuple, TypedDict

if TYPE_CHECKING:
    import aiohttp

API_BASE: str = "https://paste.myst.rs/api/v2"


class CreatePasteInput(NamedTuple):
    title: str
    language: str
    code: str


class PasteMystRsPastie(TypedDict):
    _id: str
    title: str
    language: str
    code: str


class PasteMystRsPasteCreate(TypedDict):
    title: str
    expiresIn: str
    isPrivate: bool
    isPublic: bool
    tags: str
    pasties: list[PasteMystRsPastie]


class PasteMystRsPasteCreateResponse(TypedDict):
    ownerId: str
    edits: list[str]  # unknown
    deletesAt: int  # timestamp
    isPublic: bool
    expiresIn: str
    stars: int
    createdAt: int
    isPrivate: bool
    title: str
    _id: str  # random
    tags: list[str]
    encrypted: bool
    pasties: list[PasteMystRsPastie]


def _clamp_time(when: datetime.datetime) -> str:
    now = datetime.datetime.now(datetime.UTC)

    diff = when - now
    diff_secs = diff.total_seconds()

    if diff_secs < 600:
        ret = "1h"
    elif 600 < diff_secs < 1200:
        ret = "2h"
    elif 1200 < diff_secs < 6000:
        ret = "10h"
    elif 6000 < diff_secs < 86400:
        ret = "1d"
    elif 86400 < diff_secs < 172800:
        ret = "2d"
    elif 172800 < diff_secs < 604800:
        ret = "1w"
    else:
        ret = "1m"

    return ret


async def create_paste(
    *,
    title: str,
    contents: list[CreatePasteInput],
    password: str | None = None,  # ruff: ignore[unused-function-argument] # backport
    tags: list[str] | None = None,
    expiry: datetime.datetime | None = None,
    session: aiohttp.ClientSession,
    api_token: str,
) -> tuple[str, datetime.datetime | None]:
    expiry_fmt = _clamp_time(expiry) if expiry else "never"
    tags_fmt = ",".join(tags) if tags else ""

    pasties: list[PasteMystRsPastie] = [
        {
            "_id": secrets.token_urlsafe(8),
            "language": paste_obj[1],
            "title": paste_obj[0],
            "code": paste_obj[2],
        }
        for paste_obj in contents
    ]

    json: PasteMystRsPasteCreate = {
        "title": title,
        "expiresIn": expiry_fmt,
        "isPrivate": False,
        "isPublic": False,
        "tags": tags_fmt,
        "pasties": pasties,
    }

    async with session.post(f"{API_BASE}/paste", headers={"Authorization": api_token}, json=json) as resp:
        data: PasteMystRsPasteCreateResponse = await resp.json()

    expires = datetime.datetime.fromtimestamp(data["deletesAt"], datetime.UTC) if data["deletesAt"] else None

    return f"https://paste.myst.rs/{data['_id']}", expires
