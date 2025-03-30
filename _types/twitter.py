from typing import Any, Literal, NotRequired, TypedDict

MediaType = Literal["media", "video"]


class FacetResponse(TypedDict):
    type: MediaType
    indices: dict[int, int]
    id: str
    display: str
    original: str
    replacement: str


class WebsiteResponse(TypedDict):
    url: str
    display_url: str


class AuthorResponse(TypedDict):
    id: str
    name: str
    screen_name: str
    avatar_url: str
    banner_url: str
    description: str
    location: str
    url: str
    followers: int
    following: int
    joined: str  # datetime
    likes: int
    website: WebsiteResponse
    tweets: int
    avatar_colour: str | None


class _InnerMediaVariantResponse(TypedDict):
    content_type: str
    url: str
    bitrate: NotRequired[int]  # only for video


class _InnerMediaResponse(TypedDict):
    url: str
    thumbnail_url: str
    width: int
    height: int
    format: str
    type: MediaType
    variants: dict[int, _InnerMediaVariantResponse]


class _InnerVideoMediaResponse(_InnerMediaResponse):
    duration: float


class MediaResponse(TypedDict):
    all: dict[int, _InnerMediaResponse] | None
    videos: dict[int, _InnerVideoMediaResponse] | None
    images: dict[int, _InnerMediaResponse] | None


class TweetRawTextResponse(TypedDict):
    text: str
    facets: dict[int, FacetResponse]


class TweetDetailsResponse(TypedDict):
    url: str
    id: str
    text: str | None
    raw_text: TweetRawTextResponse
    author: AuthorResponse
    replies: int
    retweets: int
    likes: int
    created_at: str  # datetime
    created_timestamp: int
    possibly_sensitive: bool
    views: int
    is_note_tweet: bool
    community_note: Any | None
    lang: str
    replying_to: str | None
    replying_to_status: str | None
    media: NotRequired[MediaResponse]
    source: str
    twitter_card: str
    color: str | None
    provider: str


class FXTwitterResponse(TypedDict):
    code: int
    message: str
    tweet: TweetDetailsResponse
