from __future__ import annotations

import operator
from typing import TYPE_CHECKING, NamedTuple, Self

import aiohttp
from dateutil.zoneinfo import get_zonefile_instance
from discord import app_commands
from discord.ext import commands
from lxml import etree  # pyright: ignore[reportAttributeAccessIssue] # lxml doesn't re-export anything so this breaks in CI

from . import fuzzy

if TYPE_CHECKING:
    from extensions.reminders import Reminder
    from utilities.context import Context

__all__ = ("CLDRDataEntry", "TimezoneHandler")


class CLDRDataEntry(NamedTuple):
    description: str
    aliases: list[str]
    deprecated: bool
    preferred: str | None


class TimeZone(NamedTuple):
    label: str
    key: str

    @classmethod
    async def convert(cls, ctx: Context[Reminder], argument: str) -> TimeZone:
        # Prioritise aliases because they handle short codes slightly better
        if argument in ctx.bot.tz_handler._timezone_aliases:
            return cls(key=ctx.bot.tz_handler._timezone_aliases[argument], label=argument)

        if argument in ctx.bot.tz_handler.valid_timezones:
            return cls(key=argument, label=argument)

        timezones = ctx.bot.tz_handler.find_timezones(argument)

        try:
            return await ctx.disambiguate(timezones, operator.itemgetter(0), ephemeral=True)
        except ValueError as err:
            msg = f"Could not find timezone for {argument!r}"
            raise commands.BadArgument(msg) from err

    def to_choice(self) -> app_commands.Choice[str]:
        return app_commands.Choice(name=self.label, value=self.key)


class TimezoneHandler:
    DEFAULT_POPULAR_TIMEZONE_IDS: tuple[str, ...] = (
        # America
        "usnyc",  # America/New_York
        "uslax",  # America/Los_Angeles
        "uschi",  # America/Chicago
        "usden",  # America/Denver
        # India
        "inccu",  # Asia/Kolkata
        # Europe
        "trist",  # Europe/Istanbul
        "rumow",  # Europe/Moscow
        "gblon",  # Europe/London
        "frpar",  # Europe/Paris
        "esmad",  # Europe/Madrid
        "deber",  # Europe/Berlin
        "grath",  # Europe/Athens
        "uaiev",  # Europe/Kyev
        "itrom",  # Europe/Rome
        "nlams",  # Europe/Amsterdam
        "plwaw",  # Europe/Warsaw
        # Canada
        "cator",  # America/Toronto
        # Australia
        "aubne",  # Australia/Brisbane
        "ausyd",  # Australia/Sydney
        # Brazil
        "brsao",  # America/Sao_Paulo
        # Japan
        "jptyo",  # Asia/Tokyo
        # China
        "cnsha",  # Asia/Shanghai
    )

    def __init__(self) -> None:
        self.valid_timezones: set[str] = set(get_zonefile_instance().zones)
        # User-friendly timezone names, some manual and most from the CLDR database.
        self._timezone_aliases: dict[str, str] = {
            "Eastern Time": "America/New_York",
            "Central Time": "America/Chicago",
            "Mountain Time": "America/Denver",
            "Pacific Time": "America/Los_Angeles",
            # (Unfortunately) special case American timezone abbreviations
            "EST": "America/New_York",
            "CST": "America/Chicago",
            "MST": "America/Denver",
            "PST": "America/Los_Angeles",
            "EDT": "America/New_York",
            "CDT": "America/Chicago",
            "MDT": "America/Denver",
            "PDT": "America/Los_Angeles",
        }
        self._default_timezones: list[app_commands.Choice[str]] = []

    @classmethod
    async def startup(cls, *, session: aiohttp.ClientSession | None = None) -> Self:
        self = cls()
        await self.parse_bcp47_timezones(session=session)

        return self

    async def parse_bcp47_timezones(self, *, session: aiohttp.ClientSession | None = None) -> None:
        resolved = session or aiohttp.ClientSession()
        async with resolved.get(
            "https://raw.githubusercontent.com/unicode-org/cldr/main/common/bcp47/timezone.xml",
        ) as resp:
            if resp.status != 200:
                return

            parser = etree.XMLParser(ns_clean=True, recover=True, encoding="utf-8")
            tree = etree.fromstring(await resp.read(), parser=parser)  # noqa: S320 # trusted source.

            # Build a temporary dictionary to resolve "preferred" mappings
            entries: dict[str, CLDRDataEntry] = {
                node.attrib["name"]: CLDRDataEntry(
                    description=node.attrib["description"],
                    aliases=node.get("alias", "Etc/Unknown").split(" "),
                    deprecated=node.get("deprecated", "false") == "true",
                    preferred=node.get("preferred"),
                )
                for node in tree.iter("type")
                # Filter the Etc/ entries (except UTC)
                if not node.attrib["name"].startswith(("utcw", "utce", "unk"))
                and not node.attrib["description"].startswith("POSIX")
            }

            for entry in entries.values():
                # These use the first entry in the alias list as the "canonical" name to use when mapping the
                # timezone to the IANA database.
                # The CLDR database is not particularly correct when it comes to these, but neither is the IANA database.
                # It turns out the notion of a "canonical" name is a bit of a mess. This works fine for users where
                # this is only used for display purposes, but it's not ideal.
                if entry.preferred is not None:
                    preferred = entries.get(entry.preferred)
                    if preferred is not None:
                        self._timezone_aliases[entry.description] = preferred.aliases[0]
                else:
                    self._timezone_aliases[entry.description] = entry.aliases[0]

            for key in self.DEFAULT_POPULAR_TIMEZONE_IDS:
                entry = entries.get(key)
                if entry is not None:
                    self._default_timezones.append(app_commands.Choice(name=entry.description, value=entry.aliases[0]))

        if not session:
            await resolved.close()

    def find_timezones(self, query: str) -> list[TimeZone]:
        # A bit hacky, but if '/' is in the query then it's looking for a raw identifier
        # otherwise it's looking for a CLDR alias
        if "/" in query:
            return [TimeZone(key=a, label=a) for a in fuzzy.finder(query, self.valid_timezones)]

        keys = fuzzy.finder(query, self._timezone_aliases.keys())
        return [TimeZone(label=k, key=self._timezone_aliases[k]) for k in keys]
