from typing import Literal, TypedDict


class PasswordAuth(TypedDict):
    access_token: str
    expires_in: int
    scope: str
    token_type: Literal["bearer"]
