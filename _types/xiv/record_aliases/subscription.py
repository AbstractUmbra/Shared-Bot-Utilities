"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

from typing import TypedDict

from asyncpg import BitString

__all__ = ("EventRecord",)


class EventRecord(TypedDict):
    """
    This is actually an asyncpg Record.
    """

    guild_id: int
    channel_id: int | None
    thread_id: int | None
    webhook_id: int
    subscriptions: BitString
    daily_role_id: int | None
    weekly_role_id: int | None
    fashion_report_role_id: int | None
    jumbo_cactpot_role_id: int | None
    ocean_fishing_role_id: int | None
    gate_role_id: int | None
    tt_open_tournament_role_id: int | None
    tt_tournament_role_id: int | None
    island_sanctuary_role_id: int | None
