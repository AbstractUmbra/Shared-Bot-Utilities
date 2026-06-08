from __future__ import annotations

from typing import Any, Literal, NotRequired, Required, TypedDict

MediaType = Literal["media", "video"]
type TwitterStatusType = TweetDetailsResponse | DeadTweetReponse | None


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


class BirthdayResponse(TypedDict):
    day: int
    month: int
    year: int


class VerificationResponse(TypedDict):
    verified: bool
    type: Literal["organization", "government", "individual"] | None
    verified_at: NotRequired[str | None]
    identity_verified: NotRequired[bool]
    verified_by: NotRequired[str]


class AccountUsernameChangesResponse(TypedDict):
    count: int
    last_changed_at: str | None


class AccountAboutResponse(TypedDict, total=False):
    based_in: str | None
    location_accurate: bool
    created_country_accurate: bool | None
    source: str | None
    username_changes: AccountUsernameChangesResponse


class AuthorResponse(TypedDict):
    type: Literal["profile"]
    id: str
    name: str
    screen_name: str
    avatar_url: str | None
    banner_url: str | None
    description: str
    raw_description: TweetRawTextResponse
    location: str
    url: str
    protected: bool
    followers: int
    following: int
    statuses: int
    media_count: int
    likes: int
    joined: str  # datetime
    website: WebsiteResponse
    birthday: NotRequired[BirthdayResponse]
    verification: NotRequired[VerificationResponse]
    about_account: NotRequired[AccountAboutResponse]
    profile_embed: NotRequired[bool]


class ExternalMediaResponse(TypedDict):
    type: Literal["video"]
    url: str
    thumbnail_url: NotRequired[str]
    height: NotRequired[int]
    width: NotRequired[int]


class PhotoMediaResponse(TypedDict):
    id: NotRequired[str]
    format: NotRequired[str]
    type: Literal["photo", "gif"]
    url: str
    width: int
    height: int
    transcode_url: NotRequired[str | None]
    alt_text: NotRequired[str]


class VideoMediaFormat(TypedDict, total=False):
    container: Literal["mp4", "webm", "m3u8"]
    codec: Literal["h264", "hevc", "vp9", "av1"]
    bitrate: int
    url: Required[str]
    size: int
    height: int
    width: int


class VideoMediaResponse(TypedDict):
    id: NotRequired[str]
    format: NotRequired[str]
    type: Literal["video"]
    url: str
    width: int
    height: int
    thumbnail_url: NotRequired[str | None]
    transcode_url: NotRequired[str | None]
    duration: int
    filesize: NotRequired[int]
    formats: list[VideoMediaFormat]
    publisher: AuthorResponse | None


class MosaicMediaFormat(TypedDict):
    webp: str
    jpeg: str


class MosaicMediaResponse(TypedDict):
    id: NotRequired[str]
    format: NotRequired[str]
    type: Literal["mosaic_photo"]
    url: str
    width: int
    height: int
    formats: MosaicMediaFormat


class BroadcastMediaResponse(TypedDict):
    url: str
    # TODO: complete types  # noqa: FIX002, TD002, TD003


class MediaResponse(TypedDict):
    external: ExternalMediaResponse
    photos: list[PhotoMediaResponse]
    videos: list[VideoMediaResponse]
    all: ExternalMediaResponse | list[PhotoMediaResponse] | list[VideoMediaResponse]
    mosaic: MosaicMediaResponse
    broadcast: BroadcastMediaResponse


class TweetRawTextResponse(TypedDict):
    text: str
    display_text_range: list[int]
    facets: dict[int, FacetResponse]


class _TwitterPollChoices(TypedDict):
    label: str
    count: int
    percentage: int


class TwitterPollDetailsResponse(TypedDict):
    choices: list[_TwitterPollChoices]
    total_votes: int
    ends_at: str
    time_left_en: str


class TweetDetailsResponse(TypedDict):
    type: Literal["status"]
    url: str
    id: str
    text: str | None
    reposts: int
    quotes: int
    replies: int
    quote: NotRequired[TwitterStatusType]
    poll: NotRequired[TwitterPollDetailsResponse]
    raw_text: TweetRawTextResponse
    author: AuthorResponse
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
    media: MediaResponse
    source: str
    twitter_card: str
    color: str | None
    provider: str


class DeadTweetReponse(TypedDict):
    type: Literal["tombstone"]
    provider: Literal["twitter"]
    reason: Literal["deleted", "unavailable", "suspended", "private", "blocked"]
    message: str
    id: NotRequired[str]
    url: NotRequired[str]
    author: NotRequired[AuthorResponse]
    at_uri: NotRequired[str]
    cid: NotRequired[str]


class FXTwitterResponse(TypedDict):
    code: int
    status: TweetDetailsResponse | DeadTweetReponse | None
    # TODO: complete types  # noqa: FIX002, TD002, TD003
    # thread: list[ThreadDetailsResponse | DeadTweetReponse] | None  # noqa: ERA001
    # author: AuthorDetailsResponse  # noqa: ERA001
