from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext.commands import ConversionError, Converter

if TYPE_CHECKING:
    from collections.abc import Hashable

    from discord import Forbidden, Message

    from .converters import MemberOrUser


LOGGER = logging.getLogger(__name__)


class LockedResourceError(RuntimeError):
    """
    Exception raised when an operation is attempted on a locked resource.

    Attributes:
        `type` -- name of the locked resource's type
        `id` -- ID of the locked resource
    """

    def __init__(self, resource_type: str, resource_id: Hashable) -> None:
        self.type = resource_type
        self.id = resource_id

        super().__init__(
            f"Cannot operate on {self.type.lower()} `{self.id}`; it is currently locked and in use by another operation.",
        )


class InvalidInfractedUserError(Exception):
    """
    Exception raised upon attempt of infracting an invalid user.

    Attributes:
        `user` -- User or Member which is invalid
    """

    def __init__(self, user: MemberOrUser, reason: str = "User infracted is a bot.") -> None:
        self.user = user
        self.reason = reason

        super().__init__(reason)


class InvalidInfractionError(ConversionError):
    """
    Raised by the Infraction converter when trying to fetch an invalid infraction id.

    Attributes:
        `infraction_arg` -- the value that we attempted to convert into an Infraction
    """

    def __init__(self, converter: Converter, original: Exception, infraction_arg: int | str) -> None:
        self.infraction_arg = infraction_arg
        super().__init__(converter, original)


class BrandingMisconfigurationError(RuntimeError):
    """Raised by the Branding cog when a misconfigured event is encountered."""


class NonExistentRoleError(ValueError):
    """
    Raised by the Information Cog when encountering a Role that does not exist.

    Attributes:
        `role_id` -- the ID of the role that does not exist
    """

    def __init__(self, role_id: int) -> None:
        super().__init__(f"Could not fetch data for role {role_id}")

        self.role_id = role_id


async def handle_forbidden_from_block(error: Forbidden, message: Message | None = None) -> None:
    """
    Handles ``discord.Forbidden`` 90001 errors, or re-raises if ``error`` isn't a 90001 error.

    Args:
        error: The raised ``discord.Forbidden`` to check.
        message: The message to reply to and include in logs, if error is 90001 and message is provided.
    """
    if error.code != 90001:
        # The error ISN'T caused by the bot attempting to add a reaction
        # to a message whose author has blocked the bot, so re-raise it
        raise error

    if not message:
        LOGGER.info("Failed to add reaction(s) to a message since the message author has blocked the bot")
        return

    if message:
        LOGGER.info(
            "Failed to add reaction(s) to message %d-%d since the message author (%d) has blocked the bot",
            message.channel.id,
            message.id,
            message.author.id,
        )
        await message.channel.send(
            f":x: {message.author.mention} failed to add reaction(s) to your message as you've blocked me.",
            delete_after=30,
        )
