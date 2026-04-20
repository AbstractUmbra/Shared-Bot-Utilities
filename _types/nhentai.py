from typing import TypedDict

__all__ = ("NHentaiCDNResponse", "NHentaiGalleryResponse")


class _LocalizedString(TypedDict):
    english: str
    japanese: str
    pretty: str


class _Image(TypedDict):
    path: str
    width: int
    height: int


class _Tag(TypedDict):
    id: int
    type: str
    name: str
    slug: str
    url: str
    count: int


class _Page(TypedDict): ...


class _CommentPoster(TypedDict):
    id: int
    username: str
    slug: str
    avatar_url: str
    is_superuser: bool
    is_staff: bool


class _Comment(TypedDict):
    id: int
    gallery_id: int
    poster: _CommentPoster
    post_date: int  # timestamp
    body: str


class _Related(TypedDict):
    id: int
    media_id: str
    english_title: str
    japanese_title: str
    thumbail: str
    thumbnail_width: str
    thumbnail_height: str
    num_pages: int
    tag_ids: list[int]
    blacklisted: bool


class NHentaiGalleryResponse(TypedDict):
    id: int
    media_id: str
    title: _LocalizedString
    cover: _Image
    thumbnail: _Image
    scanlator: str
    upload_date: int  # timestamp
    tags: list[_Tag]
    num_pages: int
    num_favorites: int
    pages: list[_Page]
    comments: list[_Comment]
    related: list[_Related]
    is_favorited: bool


class NHentaiCDNResponse(TypedDict):
    image_servers: list[str]
    thumb_servers: list[str]
