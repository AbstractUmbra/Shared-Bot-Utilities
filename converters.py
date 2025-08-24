"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from __future__ import annotations

import collections
import datetime
import logging
import operator
import re
import zoneinfo
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import discord
import yarl
from discord import Member, User, Webhook, app_commands
from discord.ext import commands

from utilities.shared.timezones import TimeZone

from .time import hf_time

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import NotRequired, Self

    from utilities.context import Context, GuildContext, Interaction

MYSTBIN_REGEX = re.compile(r"(?:(?:https?://)?(?:beta\.)?(?:mystb\.in\/))?(?P<id>(?:[A-Z]{1}[a-z]+)*)(?P<ext>\.\w+)?")
LOGGER = logging.getLogger(__name__)

__all__ = (
    "BadDatetimeTransform",
    "DatetimeConverter",
    "DatetimeTransformer",
    "MystbinPasteConverter",
    "RedditMediaURL",
    "WebhookTransformer",
    "WhenAndWhatConverter",
    "WhenAndWhatTransformer",
)


def resolve_nsfwness(
    messageable: discord.abc.Messageable | discord.CategoryChannel | discord.ForumChannel | None,
    /,
) -> bool:
    from utilities.context import Context  # noqa: PLC0415 # cheat

    if not messageable:
        # passed None
        return False

    if isinstance(messageable, Context):
        # resolve inner context
        messageable = messageable.channel

    if isinstance(messageable, (discord.User, discord.Member, discord.DMChannel, discord.GroupChannel)):
        # DMs are okay
        return True
    if isinstance(
        messageable,
        (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel, discord.ForumChannel),
    ):
        # use the channel attr
        return messageable.nsfw
    if isinstance(messageable, discord.Thread) and messageable.parent:
        # Thread has a parent
        return messageable.parent.nsfw

    return False


class DucklingNormalised(TypedDict):
    unit: Literal["second"]
    value: int


class DucklingResponseValue(TypedDict):
    normalized: DucklingNormalised
    type: Literal["value"]
    unit: str
    value: NotRequired[str]
    minute: NotRequired[int]
    hour: NotRequired[int]
    second: NotRequired[int]
    day: NotRequired[int]
    week: NotRequired[int]
    hour: NotRequired[int]


class DucklingResponse(TypedDict):
    body: str
    dim: Literal["duration", "time"]
    end: int
    start: int
    latent: bool
    value: DucklingResponseValue


class MemeDict(collections.UserDict):
    def __getitem__(self, k: Sequence[Any]) -> Any:
        for key in self:
            if k in key:
                return super().__getitem__(key)
        raise KeyError(k)


class RedditMediaURL:
    VALID_PATH = re.compile(r"/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+(?:/.+)?")

    def __init__(self, url: yarl.URL) -> None:
        self.url = url
        self.filename = url.parts[1] + ".mp4"

    @classmethod
    async def convert(cls: type[Self], ctx: Context, argument: str) -> Self:
        try:
            url = yarl.URL(argument)
        except TypeError as err:
            raise commands.BadArgument("Not a valid URL.") from err

        headers = {"User-Agent": "Discord:mipha:v1.0 (by /u/AbstractUmbra)"}
        await ctx.typing()
        if url.host == "v.redd.it":
            # have to do a request to fetch the 'main' URL.
            async with ctx.session.get(url, headers=headers) as resp:
                url = resp.url

        if url.host is None:
            raise commands.BadArgument("Not a valid v.reddit url.")

        is_valid_path = url.host.endswith(".reddit.com") and cls.VALID_PATH.match(url.path)
        if not is_valid_path:
            raise commands.BadArgument("Not a reddit URL.")

        # Now we go the long way
        async with ctx.session.get(url / ".json", headers=headers) as resp:
            if resp.status != 200:
                msg = f"Reddit API failed with {resp.status}."
                raise commands.BadArgument(msg)

            data = await resp.json()
            try:
                submission = data[0]["data"]["children"][0]["data"]
            except (KeyError, TypeError, IndexError) as err:
                raise commands.BadArgument("Could not fetch submission.") from err

            try:
                media = submission["media"]["reddit_video"]
            except (KeyError, TypeError):
                try:
                    # maybe it's a cross post
                    crosspost = submission["crosspost_parent_list"][0]
                    media = crosspost["media"]["reddit_video"]
                except (KeyError, TypeError, IndexError) as err:
                    raise commands.BadArgument("Could not fetch media information.") from err

            try:
                fallback_url = yarl.URL(media["fallback_url"])
            except KeyError as err:
                raise commands.BadArgument("Could not fetch fall back URL.") from err

            return cls(fallback_url)


class DatetimeConverter(commands.Converter[datetime.datetime]):
    @staticmethod
    async def get_timezone(ctx: Context) -> zoneinfo.ZoneInfo | None:
        row: str | None = await ctx.bot.pool.fetchval("SELECT tz FROM tz_store WHERE user_id = $1;", ctx.author.id)
        return zoneinfo.ZoneInfo(row) if row else zoneinfo.ZoneInfo("UTC")

    @classmethod
    async def parse(
        cls,
        argument: str,
        /,
        *,
        ctx: Context,
        timezone: datetime.tzinfo | None = datetime.UTC,
        now: datetime.datetime | None = None,
        duckling_url: yarl.URL,
    ) -> list[tuple[datetime.datetime, int, int]]:
        now = now or datetime.datetime.now(datetime.UTC)

        times: list[tuple[datetime.datetime, int, int]] = []

        async with ctx.bot.session.post(
            duckling_url,
            data={
                "locale": "en_US",
                "text": argument,
                "dims": '["time", "duration"]',
                "tz": str(timezone),
            },
        ) as response:
            data: list[DucklingResponse] = await response.json()

            for time in data:
                if time["dim"] == "time" and "value" in time["value"]:
                    times.append(
                        (
                            datetime.datetime.fromisoformat(time["value"]["value"]),
                            time["start"],
                            time["end"],
                        ),
                    )
                elif time["dim"] == "duration":
                    times.append(
                        (
                            datetime.datetime.now(datetime.UTC)
                            + datetime.timedelta(seconds=time["value"]["normalized"]["value"]),
                            time["start"],
                            time["end"],
                        ),
                    )

        return times

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> datetime.datetime:
        timezone = await cls.get_timezone(ctx)
        now = ctx.message.created_at.astimezone(tz=timezone)

        duckling_key = ctx.bot.config.get("duckling")
        if not duckling_key:
            raise RuntimeError("No Duckling instance available to perform this action.")

        duckling_url = yarl.URL.build(
            scheme="http",
            host=duckling_key["host"],
            port=duckling_key["port"],
            path="/parse",
        )

        parsed_times = await cls.parse(argument, ctx=ctx, timezone=timezone, now=now, duckling_url=duckling_url)

        if len(parsed_times) == 0:
            raise commands.BadArgument("Could not parse time.")
        if len(parsed_times) > 1:
            ...

        return parsed_times[0][0]


class WhenAndWhatConverter(commands.Converter[tuple[datetime.datetime, str]]):
    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> tuple[datetime.datetime, str]:
        timezone = await DatetimeConverter.get_timezone(ctx)
        now = ctx.message.created_at.astimezone(tz=timezone)

        # Strip some common stuff
        for prefix in ("me to ", "me in ", "me at ", "me that "):
            if argument.startswith(prefix):
                argument = argument[len(prefix) :]
                break

        for suffix in ("from now",):
            argument = argument.removesuffix(suffix)

        argument = argument.strip()

        duckling_key = ctx.bot.config.get("duckling")
        if not duckling_key:
            raise RuntimeError("No Duckling instance available to perform this action.")

        duckling_url = yarl.URL.build(
            scheme="http",
            host=duckling_key["host"],
            port=duckling_key["port"],
            path="/parse",
        )

        # Determine the date argument
        parsed_times = await DatetimeConverter.parse(
            argument,
            ctx=ctx,
            timezone=timezone,
            now=now,
            duckling_url=duckling_url,
        )

        if len(parsed_times) == 0:
            raise commands.BadArgument("Could not parse time.")
        if len(parsed_times) > 1:
            ...

        when, begin, end = parsed_times[0]

        if begin != 0 and end != len(argument):
            raise commands.BadArgument("Could not distinguish time from argument.")

        if when < now:
            raise commands.BadArgument("This time is in the past.")

        what = argument[end + 1 :].lstrip(" ,.!:;") if begin == 0 else argument[:begin].strip()

        for prefix in ("to ",):
            what = what.removeprefix(prefix)

        return (when, what or "…")


class BadDatetimeTransform(app_commands.AppCommandError):
    pass


class TimezoneTransformer(app_commands.Transformer):
    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.string

    async def autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:  # override
        tzs = interaction.client.tz_handler.find_timezones(current)
        return [tz.to_choice() for tz in tzs][:25]

    async def transform(self, interaction: Interaction, value: str) -> TimeZone:  # override
        if value in interaction.client.tz_handler.timezone_aliases:
            return TimeZone(key=interaction.client.tz_handler.timezone_aliases[value], label=value)

        if value in interaction.client.tz_handler.valid_timezones:
            return TimeZone(key=value, label=value)

        tzs = interaction.client.tz_handler.find_timezones(value)

        from utilities.context import Context  # noqa: PLC0415 # cheat

        ctx = await Context.from_interaction(interaction)

        try:
            return await ctx.disambiguate(tzs, operator.itemgetter(0), ephemeral=True)
        except ValueError:
            msg = f"Could not find timezone for {value}."
            raise app_commands.AppCommandError(msg) from None


class DatetimeTransformer(app_commands.Transformer):
    @staticmethod
    async def get_timezone(interaction: Interaction) -> zoneinfo.ZoneInfo | None:
        row: str | None = await interaction.client.pool.fetchval(
            "SELECT tz FROM tz_store WHERE user_id = $1;",
            interaction.user.id,
        )
        return zoneinfo.ZoneInfo(row) if row else zoneinfo.ZoneInfo("UTC")

    @classmethod
    async def parse(
        cls,
        argument: str,
        /,
        *,
        interaction: Interaction,
        timezone: datetime.tzinfo | None = datetime.UTC,
        now: datetime.datetime | None = None,
        duckling_url: yarl.URL,
    ) -> list[tuple[datetime.datetime, int, int]]:
        now = now or datetime.datetime.now(datetime.UTC)

        times: list[tuple[datetime.datetime, int, int]] = []

        async with interaction.client.session.post(
            duckling_url,
            data={
                "locale": "en_US",
                "text": argument,
                "dims": '["time", "duration"]',
                "tz": str(timezone),
            },
        ) as response:
            data: list[DucklingResponse] = await response.json()

            for time in data:
                if time["dim"] == "time" and "value" in time["value"]:
                    times.append(
                        (
                            datetime.datetime.fromisoformat(time["value"]["value"]).astimezone(timezone),
                            time["start"],
                            time["end"],
                        ),
                    )
                elif time["dim"] == "duration":
                    times.append(
                        (
                            datetime.datetime.now(timezone)
                            + datetime.timedelta(seconds=time["value"]["normalized"]["value"]),
                            time["start"],
                            time["end"],
                        ),
                    )

        return times

    @classmethod
    async def transform(cls, interaction: Interaction, argument: str) -> datetime.datetime:
        timezone = await cls.get_timezone(interaction)
        now = interaction.created_at.astimezone(tz=timezone)

        duckling_key = interaction.client.config.get("duckling")
        if not duckling_key:
            raise RuntimeError("No Duckling instance available to perform this action.")

        duckling_url = yarl.URL.build(
            scheme="http",
            host=duckling_key["host"],
            port=duckling_key["port"],
            path="/parse",
        )

        parsed_times = await cls.parse(
            argument,
            interaction=interaction,
            timezone=timezone,
            now=now,
            duckling_url=duckling_url,
        )

        if len(parsed_times) == 0:
            raise BadDatetimeTransform("Could not parse time.")
        if len(parsed_times) > 1:
            ...

        return parsed_times[0][0]

    async def autocomplete(self, interaction: Interaction, value: str) -> list[app_commands.Choice[str]]:
        if not value:
            return []

        duckling_key = interaction.client.config.get("duckling")
        if not duckling_key:
            raise RuntimeError("No Duckling instance available to perform this action.")

        duckling_url = yarl.URL.build(
            scheme="http",
            host=duckling_key["host"],
            port=duckling_key["port"],
            path="/parse",
        )
        tz = await self.get_timezone(interaction)

        now = interaction.created_at.astimezone(tz=tz)
        parsed_times = await self.parse(
            value,
            timezone=tz,
            now=now,
            interaction=interaction,
            duckling_url=duckling_url,
        )

        return [app_commands.Choice(name=hf_time(when, with_time=True), value=value) for when, _, _ in parsed_times]


class WhenAndWhatTransformer(DatetimeTransformer):
    @classmethod
    async def transform(cls, interaction: Interaction, value: str) -> datetime.datetime:
        timezone = await cls.get_timezone(interaction)
        now = interaction.created_at.astimezone(tz=timezone)

        # Strip some common stuff
        for prefix in ("me to ", "me in ", "me at ", "me that "):
            if value.startswith(prefix):
                value = value[len(prefix) :]
                break

        for suffix in ("from now",):
            value = value.removesuffix(suffix)

        value = value.strip()

        duckling_key = interaction.client.config.get("duckling")
        if not duckling_key:
            raise RuntimeError("No Duckling instance available to perform this action.")

        duckling_url = yarl.URL.build(
            scheme="http",
            host=duckling_key["host"],
            port=duckling_key["port"],
            path="/parse",
        )

        parsed_times = await cls.parse(
            value,
            interaction=interaction,
            timezone=timezone,
            now=now,
            duckling_url=duckling_url,
        )

        if len(parsed_times) == 0:
            raise BadDatetimeTransform("Could not parse time.")
        if len(parsed_times) > 1:
            ...

        when, begin, end = parsed_times[0]

        if begin != 0 and end != len(value):
            raise BadDatetimeTransform("Could not distinguish time from argument.")

        if when < now:
            raise BadDatetimeTransform("This time is in the past.")

        what = value[end + 1 :].lstrip(" ,.!:;") if begin == 0 else value[:begin].strip()

        for prefix in ("to ",):
            what = what.removeprefix(prefix)

        return when

    async def autocomplete(self, interaction: Interaction, value: str) -> list[app_commands.Choice[str]]:
        raise NotImplementedError("Not meant for this subclass.")


# This is because Discord is stupid with Slash Commands and doesn't actually have integer types.
# So to accept snowflake inputs you need a string and then convert it into an integer.
class Snowflake:
    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> int:
        try:
            return int(argument)
        except ValueError as err:
            param = ctx.current_parameter
            if param:
                msg = f"{param.name} argument expected a Discord ID not {argument!r}"
                raise commands.BadArgument(msg) from err
            msg = f"expected a Discord ID not {argument!r}"
            raise commands.BadArgument(msg) from err


class MystbinPasteConverter(commands.Converter[str]):
    async def convert(self, _: GuildContext, argument: str) -> str:
        matches = MYSTBIN_REGEX.search(argument)
        if not matches:
            raise commands.ConversionError(self, ValueError("No Mystbin IDs found in this text."))

        return matches["id"]


class WebhookTransformer(app_commands.Transformer):
    async def transform(self, interaction: Interaction, value: str) -> Webhook:
        try:
            wh = Webhook.from_url(value, client=interaction.client, session=interaction.client.session)
        except ValueError as err:
            await interaction.response.send_message(
                "Sorry but the provided webhook url is invalid. Perhaps a typo?",
                ephemeral=True,
            )
            raise ValueError from err

        return wh


MemberOrUser = Member | User
