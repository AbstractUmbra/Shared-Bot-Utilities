from __future__ import annotations

from typing import Literal, TypedDict

__all__ = ("ReportStateResponse",)

SlotTypes = Literal["weapon", "head", "body", "hands", "legs", "feet"]


class _OptionsHints(TypedDict):
    hint: str
    slot: str
    ringNote: str


class OptionsResponse(TypedDict):
    week: str
    reportTitle: str
    hints: list[_OptionsHints]


class DyeDataResponse(TypedDict):
    plus1: str
    plus2: str


class _ItemPair(TypedDict):
    slot: str
    name: str


class ScoreResponse(TypedDict):
    itemPairs: list[_ItemPair]
    dyes: dict[SlotTypes, str]
    _updatedAt: int  # timestamp


class LinksResponse(TypedDict):
    theorycraft: str
    results: str


class ReportStateResponse(TypedDict):
    lastOptions: OptionsResponse
    dyeData: dict[SlotTypes, DyeDataResponse]
    easy100: ScoreResponse
    easy80: ScoreResponse
    links: LinksResponse
    dyesFresh: bool
    easy100Fresh: bool
    easy80Fresh: bool
