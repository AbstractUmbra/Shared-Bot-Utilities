from typing import TypedDict

__all__ = ("RTFSResponse",)


class RTFMData(TypedDict):
    source: str
    url: str


class RTFSResponse(TypedDict):
    nodes: dict[str, RTFMData]
    query_time: float
    commit: str
