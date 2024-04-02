from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import aiohttp

AUTH_ROUTE_BASE = "https://www.reddit.com/api/v1"
ROUTE_BASE = "https://oauth.reddit.com/"

if TYPE_CHECKING:
    from utilities.shared._types.bot_config import RedditConfig
    from utilities.shared._types.xiv.reddit.auth import PasswordAuth

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
    __handler: SecretHandler

    __slots__ = ("__handler",)

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
        return datetime.datetime.now(datetime.UTC) > self.__handler.expires

    def to_bearer(self) -> str:
        return f"Bearer {self.__handler.token}"

    async def refresh(self, *, session: aiohttp.ClientSession, config: RedditConfig) -> Self:
        basic_auth = aiohttp.BasicAuth(config["client_id"], config["client_secret"])
        body = {
            "username": config["username"],
            "password": config["password"],
            "grant_type": "password",
            "scope": "history read",
        }
        headers = {"User-Agent": config["user_agent"]}

        async with (
            session.post(f"{AUTH_ROUTE_BASE}/access_token", data=body, auth=basic_auth, headers=headers) as resp,
        ):
            response: PasswordAuth = await resp.json()

        if hasattr(self, "__handler"):
            self.__handler._update_from_payload(response)
        else:
            self.__handler = SecretHandler(
                response["access_token"], expires=response["expires_in"], scopes=response["scope"]
            )
        return self

    async def revoke(self, *, session: aiohttp.ClientSession, config: RedditConfig) -> None:
        body_data = {"token": self.__handler.token, "token_type_hint": "access_token"}
        headers = {"User-Agent": config["user_agent"]}
        auth = aiohttp.BasicAuth(config["client_id"], config["client_secret"])
        await session.post(f"{AUTH_ROUTE_BASE}/revoke_token", headers=headers, data=body_data, auth=auth)
