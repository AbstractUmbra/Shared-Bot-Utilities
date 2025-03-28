"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

from __future__ import annotations

import datetime
import secrets
import traceback
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from typing import Self

    from extensions.stats import Stats
    from utilities.context import Interaction

__all__ = ("BaseModal", "BaseView", "ConfirmationView", "SelfDeleteView")


class BaseModal(discord.ui.Modal):
    async def on_error(
        self,
        interaction: Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        e = discord.Embed(title="IRLs Modal Error", colour=0xA32952)
        e.add_field(name="Modal", value=self.__class__.__name__, inline=False)

        (exc_type, exc, tb) = type(error), error, error.__traceback__
        trace = "\n".join(traceback.format_exception(exc_type, exc, tb))

        e.add_field(name="Error", value=f"```py\n{trace}\n```")
        e.timestamp = datetime.datetime.now(datetime.UTC)

        stats: Stats | None = interaction.client.get_cog("Stats")  # pyright: ignore[reportAssignmentType] # type downcasting
        if not stats:
            return

        try:
            await stats.webhook.send(embed=e)
        except discord.HTTPException:
            pass


class BaseView(discord.ui.View):
    message: discord.Message | discord.PartialMessage

    @property
    def buttons(self) -> list[discord.ui.Button[Self]]:
        return [*filter(lambda c: isinstance(c, discord.ui.Button), self.children)]  # pyright: ignore[reportReturnType] # filter predicate isn't a valid typeguard

    async def on_error(
        self,
        interaction: Interaction,
        error: Exception,
        item: discord.ui.Item[Self],
        /,
    ) -> None:
        view_name = self.__class__.__name__
        interaction.client.log_handler.log.exception(
            "Exception occurred in View %r:\n%s",
            view_name,
            error,
        )

        embed = discord.Embed(title=f"{view_name} View Error", colour=0xA32952)
        embed.add_field(name="Author", value=interaction.user, inline=False)
        channel = interaction.channel
        assert channel

        name, id_ = (
            (channel.name, channel.id)
            if isinstance(channel, discord.TextChannel)
            else (f"DMs with {interaction.user} ({interaction.user.id})", channel.id)
        )
        guild = interaction.guild
        location_fmt = f"Channel: {name} ({id_})"

        if guild:
            location_fmt += f"\nGuild: {guild.name} ({guild.id})"
            embed.add_field(name="Location", value=location_fmt, inline=True)

        (exc_type, exc, tb) = type(error), error, error.__traceback__
        trace = traceback.format_exception(exc_type, exc, tb)
        clean = "".join(trace)
        if len(clean) >= 2000:
            password = secrets.token_urlsafe(16)
            paste = await interaction.client.create_paste(content=clean, password=password)
            embed.description = (
                f"Error was too long to send in a codeblock, so I have pasted it [here]({paste})."
                f"\nThe password is `{password}`."
            )
        else:
            embed.description = f"```py\n{clean}\n```"

        embed.timestamp = datetime.datetime.now(datetime.UTC)
        await interaction.client.logging_webhook.send(embed=embed)
        await interaction.client.owner.send(embed=embed)

    def _enable_all_buttons(self) -> None:
        for button in self.children:
            if isinstance(button, discord.ui.Button):
                button.disabled = False

    def _disable_all_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def on_timeout(self) -> None:
        self._disable_all_buttons()
        await self.message.edit(view=self)


class SelfDeleteView(BaseView):
    def __init__(self, *, timeout: float = 16.0, author_id: int) -> None:
        super().__init__(timeout=timeout)
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.grey, label="Author and Moderators can delete this message!", disabled=True
            )
        )
        self.author_id = author_id

    def _can_remove(self, interaction: Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True

        return bool(
            interaction.guild
            and interaction.channel
            and isinstance(interaction.channel, discord.abc.GuildChannel)
            and isinstance(interaction.user, discord.Member)
            and interaction.channel.permissions_for(interaction.user).manage_messages,
        )

    async def on_timeout(self) -> None:
        await self.message.edit(view=None)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="\U0001f5d1\U0000fe0f")
    async def delete_callback(self, interaction: Interaction, item: discord.ui.Item[Self]) -> None:
        await interaction.response.defer(ephemeral=True)

        if not self._can_remove(interaction):
            return await interaction.followup.send("Sorry, you can't delete this.", ephemeral=True)

        return await self.message.delete()


class ConfirmationView(BaseView):
    def __init__(self, *, timeout: float, author_id: int, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: bool | None = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "This confirmation dialog is not for you.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        if self.delete_after and self.message:
            if not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(
                    view=None,
                    content="This is safe to dismiss now.",
                )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self,
        interaction: Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.value = True
        await interaction.response.defer()
        if self.delete_after and self.message:
            await interaction.delete_original_response()
        else:
            await interaction.edit_original_response(view=None)

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: Interaction, button: discord.ui.Button) -> None:
        self.value = False
        await interaction.response.defer()
        if self.delete_after and self.message:
            await interaction.delete_original_response()
        else:
            await interaction.edit_original_response(view=None)

        self.stop()
