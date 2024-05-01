from typing import TypedDict

__all__ = ("YokaiConfig",)


class YokaiWeapon(TypedDict):
    name: str
    job: str
    url: str


class Yokai(TypedDict):
    id: int
    url: str
    areas: list[str]
    weapon: YokaiWeapon


class YokaiConfig(TypedDict):
    infographic: str
    event: str
    weapons: str
    mounts: list[str]
    yokai: dict[str, Yokai]
