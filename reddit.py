from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import aiohttp
from discord.utils import MISSING

AUTH_ROUTE_BASE = "https://www.reddit.com/api/v1"
ROUTE_BASE = "https://oauth.reddit.com/"

if TYPE_CHECKING:
    from ._types.bot_config import RedditConfig
    from ._types.xiv.reddit.auth import PasswordAuth

__all__ = ("AuthHandler",)


class SecretHandler:
    __slots__ = (
        "token",
        "expires",
        "_scopes",
    )

    def __init__(self, token: str, expires: int, scopes: str) -> None:
        self.token = token
        self.expires = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expires)
        self._scopes = scopes

    def __repr__(self) -> str:
        return "<SecretHandler>"

    @property
    def scopes(self) -> list[str]:
        return self._scopes.split(" ")

    def _update_from_payload(self, data: PasswordAuth) -> Self:
        self.token = data["access_token"]
        self.expires = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=data["expires_in"])
        self._scopes = data["scope"]

        return self


class AuthHandler:
    __slots__ = (
        "__handler",
        "session",
        "config",
    )

    def __init__(self, *, session: aiohttp.ClientSession, config: RedditConfig) -> None:
        self.session = session
        self.config = config
        self.__handler: SecretHandler = MISSING

    @property
    def token(self) -> str:
        return self.__handler.token

    @property
    def scopes(self) -> list[str]:
        return self.__handler.scopes

    @property
    def expires(self) -> datetime.datetime:
        return self.__handler.expires

    def has_expired(self) -> bool:
        if self.__handler is MISSING:
            return True
        return datetime.datetime.now(datetime.UTC) > self.__handler.expires

    def to_bearer(self) -> str:
        return f"Bearer {self.__handler.token}"

    async def refresh(self) -> Self:
        if not self.has_expired():
            return self

        basic_auth = aiohttp.BasicAuth(self.config["client_id"], self.config["client_secret"])
        body = {
            "username": self.config["username"],
            "password": self.config["password"],
            "grant_type": "password",
            "scope": "history read",
        }
        headers = {"User-Agent": self.config["user_agent"]}

        async with (
            self.session.post(f"{AUTH_ROUTE_BASE}/access_token", data=body, auth=basic_auth, headers=headers) as resp,
        ):
            response: PasswordAuth = await resp.json()

        if hasattr(self, "__handler"):
            self.__handler._update_from_payload(response)
        else:
            self.__handler = SecretHandler(
                response["access_token"], expires=response["expires_in"], scopes=response["scope"]
            )
        return self

    async def revoke(self) -> None:
        body_data = {"token": self.__handler.token, "token_type_hint": "access_token"}
        headers = {"User-Agent": self.config["user_agent"]}
        auth = aiohttp.BasicAuth(self.config["client_id"], self.config["client_secret"])
        await self.session.post(f"{AUTH_ROUTE_BASE}/revoke_token", headers=headers, data=body_data, auth=auth)
