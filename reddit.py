from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, Self, TypedDict, TypeVar

import aiohttp
from discord.utils import MISSING

AUTH_ROUTE_BASE = "https://www.reddit.com/api/v1"
ROUTE_BASE = "https://oauth.reddit.com/"

if TYPE_CHECKING:
    from ._types.xiv.reddit.auth import PasswordAuth

__all__ = (
    "RedditHandler",
    "RedditError",
)

T = TypeVar("T")

LOGGER = logging.getLogger(__name__)


class RedditError(Exception):
    pass


class RedditConfig(TypedDict):
    client_id: str
    client_secret: str
    username: str
    password: str
    user_agent: str


class _RedditSecretHandler:
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


class RedditHandler:
    __slots__ = (
        "__handler",
        "session",
        "config",
        "headers",
    )

    def __init__(self, *, session: aiohttp.ClientSession, config: RedditConfig) -> None:
        self.session = session
        self.config = config
        self.headers = {"User-Agent": self.config["user_agent"]}
        self.__handler: _RedditSecretHandler = MISSING

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

    async def get_token(self) -> Self:
        if not self.has_expired():
            return self

        return await self.refresh()

    async def refresh(self) -> Self:
        basic_auth = aiohttp.BasicAuth(self.config["client_id"], self.config["client_secret"])
        body = {
            "username": self.config["username"],
            "password": self.config["password"],
            "grant_type": "password",
            "scope": "history read",
        }

        async with (
            self.session.post(f"{AUTH_ROUTE_BASE}/access_token", data=body, auth=basic_auth, headers=self.headers) as resp,
        ):
            response: PasswordAuth = await resp.json()

        self.__handler = _RedditSecretHandler(
            response["access_token"], expires=response["expires_in"], scopes=response["scope"]
        )
        return self

    async def revoke(self) -> None:
        body_data = {"token": self.__handler.token, "token_type_hint": "access_token"}
        headers = {"User-Agent": self.config["user_agent"]}
        auth = aiohttp.BasicAuth(self.config["client_id"], self.config["client_secret"])
        await self.session.post(f"{AUTH_ROUTE_BASE}/revoke_token", headers=headers, data=body_data, auth=auth)

    async def get(self, url: str, *, limit: int = 10) -> Any:
        token_handler = await self.get_token()
        headers = self.headers.copy()
        headers.update({"Authorization": token_handler.to_bearer()})
        async with self.session.get(url, headers=headers, params={"limit": limit}) as resp:
            if not resp.ok:
                LOGGER.error("The API request to Reddit has failed with the status code: '%s'", resp.status)
                raise ValueError("Reddit API request failed.")

            return await resp.json()
