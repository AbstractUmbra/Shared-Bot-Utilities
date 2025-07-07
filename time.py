"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from __future__ import annotations

import datetime
import enum
import re
import traceback
from typing import TYPE_CHECKING

import parsedatetime as pdt
from dateutil.relativedelta import relativedelta
from discord.ext import commands

from .formats import human_join, plural

if TYPE_CHECKING:
    from utilities.context import Context

# Monkey patch mins and secs into the units
units = pdt.pdtLocales["en_US"].units
units["minutes"].append("mins")
units["seconds"].append("secs")
units["hours"].append("hr")
units["hours"].append("hrs")


class Weekday(enum.Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


class ShortTime:
    compiled = re.compile(
        r"""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """,
        re.VERBOSE,
    )

    def __init__(self, argument: str, *, now: datetime.datetime | None = None) -> None:
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument("invalid time provided")

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.now(datetime.UTC)
        self.dt = now + relativedelta(**data)  # pyright: ignore[reportArgumentType] # untypable dict

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> ShortTime:
        return cls(argument, now=ctx.message.created_at)


class HumanTime:
    dt: datetime.datetime
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument: str, *, now: datetime.datetime | None = None) -> None:
        now = now or datetime.datetime.now(datetime.UTC)
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        assert isinstance(status, pdt.pdtContext)
        if not status.hasDateOrTime:
            raise commands.BadArgument(
                'invalid time provided, try e.g. "tomorrow" or "3 days"',
            )

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                microsecond=now.microsecond,
                tzinfo=datetime.UTC,
            )

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> HumanTime:
        return cls(argument, now=ctx.message.created_at)


class Time(HumanTime):
    def __init__(self, argument: str, *, now: datetime.datetime | None = None) -> None:
        try:
            o = ShortTime(argument, now=now)
        except (commands.BadArgument, ValueError):
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument: str, *, now: datetime.datetime | None = None) -> None:
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument("this time is in the past")


class UserFriendlyTime(commands.Converter):
    """That way quotes aren't absolutely necessary."""

    dt: datetime.datetime

    def __init__(
        self,
        converter: commands.Converter | None = None,
        *,
        default: str | None = None,
    ) -> None:
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            raise TypeError("commands.Converter subclass necessary.")

        self.converter = converter
        self.default = default

    async def check_constraints(
        self,
        ctx: Context,
        now: datetime.datetime,
        remaining: str,
    ) -> UserFriendlyTime:
        if self.dt < now:
            raise commands.BadArgument("This time is in the past.")

        if not remaining:
            if self.default is None:
                raise commands.BadArgument("Missing argument after the time.")
            remaining = self.default

        if self.converter is not None:
            self.arg = await self.converter.convert(ctx, remaining)
        else:
            self.arg = remaining
        return self

    def copy(self) -> UserFriendlyTime:
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.converter = self.converter
        obj.default = self.default
        return obj

    async def convert(self, ctx: Context, argument: str) -> UserFriendlyTime:
        # Create a copy of ourselves to prevent race conditions from two
        # events modifying the same instance of a converter
        result = self.copy()
        remaining = ""
        try:
            calendar = HumanTime.calendar
            regex = ShortTime.compiled
            now = ctx.message.created_at

            match = regex.match(argument)
            if match is not None and match.group(0):
                data = {k: int(v) for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end() :].strip()
                result.dt = now + relativedelta(**data)  # pyright: ignore[reportArgumentType] # untypable dict
                return await result.check_constraints(ctx, now, remaining)

            # apparently nlp does not like "from now"
            # it likes "from x" in other cases though so let me handle the 'now' case
            if argument.endswith("from now"):
                argument = argument[:-8].strip()

            if argument[0:2] == "me" and argument[0:6] in {
                "me to ",
                "me in ",
                "me at ",
            }:
                # starts with "me to", "me in", or "me at "
                argument = argument[6:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                raise commands.BadArgument(
                    'Invalid time provided, try e.g. "tomorrow" or "3 days".',
                )

            # handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time

            # first the first two cases:
            dt, status, begin, end, _ = elements[0]

            if not status.hasDateOrTime:
                raise commands.BadArgument(
                    'Invalid time provided, try e.g. "tomorrow" or "3 days".',
                )

            if begin not in {0, 1} and end != len(argument):
                raise commands.BadArgument(
                    "Time is either in an inappropriate location, which "
                    "must be either at the end or beginning of your input, "
                    "or I just flat out did not understand what you meant. Sorry.",
                )

            if not status.hasTime:
                # replace it with the current time
                dt = dt.replace(
                    hour=now.hour,
                    minute=now.minute,
                    second=now.second,
                    microsecond=now.microsecond,
                )

            # if midnight is provided, just default to next day
            if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
                dt = dt.replace(day=now.day + 1)

            result.dt = dt.replace(tzinfo=datetime.UTC)

            if begin in {0, 1}:
                if begin == 1:
                    # check if it's quoted:
                    if argument[0] != '"':
                        raise commands.BadArgument(
                            "Expected quote before time input...",
                        )

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument(
                            "If the time is quoted, you must unquote it.",
                        )

                    remaining = argument[end + 1 :].lstrip(" ,.!")
                else:
                    remaining = argument[end:].lstrip(" ,.!")
            elif len(argument) == end:
                remaining = argument[:begin].strip()

            return await result.check_constraints(ctx, now, remaining)
        except Exception:
            traceback.print_exc()
            raise


def human_timedelta(
    dt: datetime.datetime,
    *,
    source: datetime.datetime | None = None,
    accuracy: int | None = 3,
    brief: bool = False,
    suffix: bool = True,
) -> str:
    now = source or (datetime.datetime.now(datetime.UTC))
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        str_suffix = ""
    else:
        delta = relativedelta(now, dt)
        str_suffix = " ago" if suffix else ""

    attrs: list[tuple[str, str]] = [
        ("year", "y"),
        ("month", "mo"),
        ("day", "d"),
        ("hour", "h"),
        ("minute", "m"),
        ("second", "s"),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + "s")
        if not elem:
            continue

        if attr == "day":
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), "week"))
                else:
                    output.append(f"{weeks}w")

        if elem <= 0:
            continue

        if brief:
            output.append(f"{elem}{brief_attr}")
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return "now"
    if not brief:
        return human_join(output, final="and") + str_suffix
    return " ".join(output) + str_suffix


def ordinal(number: int) -> str:
    return f"{number}{'tsnrhtdd'[(number // 10 % 10 != 1) * (number % 10 < 4) * number % 10 :: 4]}"


def hf_time(dt: datetime.datetime, *, with_time: bool = True) -> str:
    date_modif = ordinal(dt.day)
    if with_time:
        return dt.strftime(f"%A {date_modif} of %B %Y @ %H:%M %Z (%z)")
    return dt.strftime(f"%A {date_modif} of %B %Y")


def resolve_next_weekday(
    *,
    target: Weekday,
    source: datetime.datetime | None = None,
    current_week_included: bool = False,
    before_time: datetime.time | None = None,
) -> datetime.datetime:
    source = source or datetime.datetime.now(datetime.UTC)
    weekday = source.weekday()

    if weekday == target.value:
        if (
            current_week_included and (before_time and source.time().replace(tzinfo=before_time.tzinfo) < before_time)
        ) or not before_time:
            return source
        return source + datetime.timedelta(days=7)

    while source.weekday() != target.value:
        source += datetime.timedelta(days=1)

    return source


def resolve_previous_weekday(
    *,
    target: Weekday,
    source: datetime.datetime | None = None,
    current_week_included: bool = False,
) -> datetime.datetime:
    source = source or datetime.datetime.now(datetime.UTC)
    weekday = source.weekday()

    if weekday == target.value:
        if current_week_included:
            return source
        return source + datetime.timedelta(days=7)

    while source.weekday() != target.value:
        source -= datetime.timedelta(days=1)

    return source
