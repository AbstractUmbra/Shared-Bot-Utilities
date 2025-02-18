"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from __future__ import annotations

import logging
from contextlib import suppress
from functools import partial
from textwrap import shorten
from typing import TYPE_CHECKING, Any, TypeVar, overload

import discord
from discord.ext import menus
from discord.ext.commands import Paginator as CommandPaginator

from .scheduling import create_task
from .ui import BaseView

LOGGER = logging.getLogger(__name__)

try:
    import hondana  # pyright: ignore[reportMissingImports]  # may not always exist
except ModuleNotFoundError:
    HAS_HONDANA = False
else:
    HAS_HONDANA = True

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from utilities.context import Context, Interaction

T = TypeVar("T")
SourceT = TypeVar("SourceT", bound="menus.PageSource")
RoboPagesT = TypeVar("RoboPagesT", bound="RoboPages")
SimplePagesT = TypeVar("SimplePagesT", bound="SimplePages")


def reaction_check(
    reaction: discord.Reaction,
    user: discord.abc.User,
    *,
    message_id: int,
    allowed_emoji: Sequence[str],
    allowed_users: Sequence[int],
    allowed_roles: Sequence[int] | None = None,
) -> bool:
    """
    Check if a reaction's emoji and author are allowed and the message is `message_id`.

    If the user is not allowed, remove the reaction. Ignore reactions made by the bot.
    If `allow_mods` is True, allow users with moderator roles even if they're not in `allowed_users`.
    """
    right_reaction = not user.bot and reaction.message.id == message_id and str(reaction.emoji) in allowed_emoji
    if not right_reaction:
        return False

    allowed_roles = allowed_roles or []
    has_sufficient_roles = any(role.id in allowed_roles for role in getattr(user, "roles", []))

    if user.id in allowed_users or has_sufficient_roles:
        LOGGER.debug("Allowed reaction %s by %s on %s.", reaction, user, reaction.message.id)
        return True

    LOGGER.debug("Removing reaction %s by %s on %s: disallowed user.", reaction, user, reaction.message.id)
    create_task(
        reaction.message.remove_reaction(reaction.emoji, user),
        suppressed_exceptions=(discord.HTTPException,),
        name=f"remove_reaction-{reaction}-{reaction.message.id}-{user}",
    )
    return False


class NumberedPageModal(discord.ui.Modal, title="Go to page"):
    page = discord.ui.TextInput["Self"](label="Page", placeholder="Enter a number", min_length=1)

    def __init__(self, max_pages: int | None) -> None:
        super().__init__()
        if max_pages is not None:
            as_string = str(max_pages)
            self.page.placeholder = f"Enter a number between 1 and {as_string}"
            self.page.max_length = len(as_string)

    async def on_submit(self, interaction: Interaction) -> None:
        self.interaction = interaction
        self.stop()


class RoboPages(BaseView):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: Context,
        check_embeds: bool = True,
        compact: bool = False,
    ) -> None:
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: Context = ctx
        self.message: discord.Message | None = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)
            if not self.compact:
                self.add_item(self.go_to_current_page)
            self.add_item(self.go_to_next_page)
            if use_last_and_first:
                self.add_item(self.go_to_last_page)
            if not self.compact:
                self.add_item(self.numbered_page)
            self.add_item(self.stop_pages)

    async def _get_kwargs_from_page(self, page: int) -> dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return {"content": value, "embed": None}
        if isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        return {}

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = max_pages is None or (page_number + 1) >= max_pages
            self.go_to_next_page.disabled = max_pages is not None and (page_number + 1) >= max_pages
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "…"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "…"

    async def show_checked_page(self, interaction: Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user and interaction.user.id in (self.ctx.bot.owner_id, self.ctx.author.id):
            return True
        await interaction.response.send_message("This pagination menu cannot be controlled by you, sorry!", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    async def on_error(self, interaction: Interaction, error: Exception, item: discord.ui.Item) -> None:
        if interaction.response.is_done():
            await interaction.followup.send("An unknown error occurred, sorry", ephemeral=True)
        else:
            await interaction.response.send_message("An unknown error occurred, sorry", ephemeral=True)

    async def start(self, *, content: str | None = None, ephemeral: bool = False) -> None:
        if self.check_embeds and not self.ctx.channel.permissions_for(self.ctx.me).embed_links:  # pyright: ignore[reportArgumentType] # guarded earlier
            await self.ctx.send("Bot does not have embed links permission in this channel.", ephemeral=True)
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        if content:
            kwargs.setdefault("content", content)

        self._update_labels(0)
        self.message = await self.ctx.send(**kwargs, view=self, ephemeral=ephemeral)

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Current", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)  # pyright: ignore[reportOperatorIssue] # PageSource isn't an ABC when it should be

    @discord.ui.button(label="Skip to page...", style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """lets you type a page number to go to"""
        if self.message is None:
            return

        modal = NumberedPageModal(self.source.get_max_pages())
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()

        if timed_out:
            await interaction.followup.send("Took too long", ephemeral=True)
            return
        if self.is_finished():
            await modal.interaction.response.send_message("Took too long", ephemeral=True)
            return

        value = str(modal.page.value)
        if not value.isdigit():
            await modal.interaction.response.send_message(f"Expected a number not {value!r}", ephemeral=True)
            return

        value = int(value)
        await self.show_checked_page(modal.interaction, value - 1)
        if not modal.interaction.response.is_done():
            error = modal.page.placeholder.replace("Enter", "Expected")  # pyright: ignore[reportOptionalMemberAccess] # Won't ever be none here
            await modal.interaction.response.send_message(error, ephemeral=True)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: Interaction, button: discord.ui.Button) -> None:
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class FieldPageSource[RoboPagesT: "RoboPages"](menus.ListPageSource):
    """A page source that requires (field_name, field_value) tuple items."""

    def __init__(
        self,
        entries: list[tuple[Any, Any]],
        *,
        per_page: int = 12,
        inline: bool = False,
        clear_description: bool = True,
    ) -> None:
        super().__init__(entries, per_page=per_page)
        self.embed: discord.Embed = discord.Embed(colour=discord.Colour.blurple())
        self.clear_description: bool = clear_description
        self.inline: bool = inline

    async def format_page(self, menu: RoboPagesT, entries: list[tuple[Any, Any]]) -> discord.Embed:
        self.embed.clear_fields()
        if self.clear_description:
            self.embed.description = None

        for key, value in entries:
            self.embed.add_field(name=key, value=value, inline=self.inline)

        maximum = self.get_max_pages()
        if maximum > 1:
            text = f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            self.embed.set_footer(text=text)

        return self.embed


class TextPageSource[RoboPagesT: "RoboPages"](menus.ListPageSource):
    def __init__(self, text: str, *, prefix: str = "```", suffix: str = "```", max_size: int = 2000) -> None:
        pages = CommandPaginator(prefix=prefix, suffix=suffix, max_size=max_size - 200)
        for line in text.split("\n"):
            pages.add_line(line)

        super().__init__(entries=pages.pages, per_page=1)

    async def format_page(self, menu: RoboPagesT, content: str) -> str:
        maximum = self.get_max_pages()
        if maximum > 1:
            return f"{content}\nPage {menu.current_page + 1}/{maximum}"
        return content


class SimplePageSource[SimplePagesT: "SimplePages"](menus.ListPageSource):
    async def format_page(self, menu: SimplePagesT, entries: Sequence[Any]) -> discord.Embed:
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f"{index + 1}. {entry}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            menu.embed.set_footer(text=footer)

        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.

    Basically an embed with some normal formatting.
    """

    def __init__(self, entries: Any, *, ctx: Context, per_page: int = 12) -> None:
        super().__init__(SimplePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.blurple())


class SimpleListSource[T](menus.ListPageSource):
    def __init__(self, data: list[T], per_page: int = 1) -> None:
        self.data = data
        super().__init__(data, per_page=per_page)

    @overload
    async def format_page(self, menu: menus.Menu, entries: list[T]) -> list[T]: ...

    @overload
    async def format_page(self, menu: menus.Menu, entries: T) -> T: ...

    async def format_page(self, menu: menus.Menu, entries: T | list[T]) -> T | list[T]:
        return entries


if HAS_HONDANA:

    class MangaDexEmbed(discord.Embed):
        @classmethod
        async def from_chapter(cls: type[Self], chapter: hondana.Chapter, *, nsfw_allowed: bool = False) -> Self:
            parent = chapter.manga
            assert parent is not None

            parent_title = parent.title
            if chapter.title:
                parent_title += f" - {chapter.title}"
            if chapter.chapter:
                parent_title += f" [Chapter {chapter.chapter}]"

            if parent.cover_url() is None:
                await parent.get_cover()

            self = cls(title=parent_title, colour=discord.Colour.red(), url=chapter.url)
            self.set_footer(text=chapter.id)
            self.timestamp = chapter.created_at
            self.add_field(name="Manga link is:", value=f"[here!]({parent.url})", inline=False)
            self.add_field(name="Number of pages:", value=chapter.pages, inline=False)
            if chapter.scanlator_groups:
                self.add_field(
                    name="Scanlator groups:",
                    value="\n".join([s.name for s in chapter.scanlator_groups]),
                    inline=False,
                )
            if chapter.uploader:
                self.add_field(name="Uploader:", value=chapter.uploader.username, inline=False)

            if parent.content_rating is hondana.ContentRating.safe or (nsfw_allowed is True):  # pyright: ignore[reportUnboundVariable] # hondana may not be installed, we're covered
                self.set_thumbnail(url=parent.cover_url())

            return self

        @classmethod
        async def from_manga(cls: type[Self], manga: hondana.Manga, *, nsfw_allowed: bool = False) -> Self:
            self = cls(title=manga.title, colour=discord.Colour.blue(), url=manga.url)
            if manga.description:
                self.description = shorten(manga.description, width=2000)
            if manga.tags:
                self.add_field(name="Tags:", value=", ".join([tag.name for tag in manga.tags]), inline=False)
            if manga.publication_demographic:
                self.add_field(name="Publication Demographic:", value=manga.publication_demographic.value.title())
            if manga.content_rating:
                self.add_field(name="Content Rating:", value=manga.content_rating.value.title(), inline=False)
            if manga.artists:
                self.add_field(name="Attributed Artists:", value=", ".join([artist.name for artist in manga.artists]))
            if manga.authors:
                self.add_field(name="Attributed Authors:", value=", ".join([artist.name for artist in manga.authors]))
            if manga.status:
                self.add_field(name="Publication status:", value=manga.status.value.title(), inline=False)
                if manga.status is hondana.MangaStatus.completed:  # pyright: ignore[reportUnboundVariable] # hondana may not be installed, we're covered
                    self.add_field(name="Last Volume:", value=manga.last_volume)
                    self.add_field(name="Last Chapter:", value=manga.last_chapter)
            self.set_footer(text=manga.id)

            if manga.content_rating is hondana.ContentRating.safe or (nsfw_allowed is True):  # pyright: ignore[reportUnboundVariable] # hondana may not be installed, we're covered
                cover = manga.cover_url() or await manga.get_cover()
                if cover:
                    self.set_image(url=manga.cover_url())

            return self


class PaginationEmojis(discord.Enum):
    first = "\u23ee"
    left = "\u2b05"
    right = "\u27a1"
    last = "\u23ed"
    delete = "\u1f6aE"


class EmptyPaginatorEmbedError(Exception):
    """Raised when attempting to paginate with empty contents."""


class _LinePaginator(CommandPaginator):
    """
    A class that aids in paginating code blocks for Discord messages.

    Args:
        pagination_emojis (PaginationEmojis): The emojis used to navigate pages.
        prefix (str): The prefix inserted to every page. e.g. three backticks.
        suffix (str): The suffix appended at the end of every page. e.g. three backticks.
        max_size (int): The maximum amount of codepoints allowed in a page.
        scale_to_size (int): The maximum amount of characters a single line can scale up to.
        max_lines (int): The maximum amount of lines allowed in a page.
    """

    def __init__(
        self,
        prefix: str = "```",
        suffix: str = "```",
        max_size: int = 4000,
        scale_to_size: int = 4000,
        max_lines: int | None = None,
        linesep: str = "\n",
    ) -> None:
        """
        This function overrides the Paginator.__init__ from inside discord.ext.commands.

        It overrides in order to allow us to configure the maximum number of lines per page.
        """
        # Embeds that exceed 4096 characters will result in an HTTPException
        # (Discord API limit), so we've set a limit of 4000
        if max_size > 4000:
            msg = f"max_size must be <= 4,000 characters. ({max_size} > 4000)"
            raise ValueError(msg)

        super().__init__(prefix, suffix, max_size - len(suffix), linesep)

        if scale_to_size < max_size:
            msg = f"scale_to_size must be >= max_size. ({scale_to_size} < {max_size})"
            raise ValueError(msg)

        if scale_to_size > 4000:
            msg = f"scale_to_size must be <= 4,000 characters. ({scale_to_size} > 4000)"
            raise ValueError(msg)

        self.scale_to_size = scale_to_size - len(suffix)
        self.max_lines = max_lines
        self._current_page = [prefix]
        self._linecount = 0
        self._count = len(prefix) + 1  # prefix + newline
        self._pages = []
        self.pagination_emoji = list(PaginationEmojis)

    def add_line(self, line: str = "", *, empty: bool = False) -> None:
        """
        Adds a line to the current page.

        If a line on a page exceeds `max_size` characters, then `max_size` will go up to
        `scale_to_size` for a single line before creating a new page for the overflow words. If it
        is still exceeded, the excess characters are stored and placed on the next pages unti
        there are none remaining (by word boundary). The line is truncated if `scale_to_size` is
        still exceeded after attempting to continue onto the next page.

        In the case that the page already contains one or more lines and the new lines would cause
        `max_size` to be exceeded, a new page is created. This is done in order to make a best
        effort to avoid breaking up single lines across pages, while keeping the total length of the
        page at a reasonable size.

        This function overrides the `Paginator.add_line` from inside `discord.ext.commands`.

        It overrides in order to allow us to configure the maximum number of lines per page.

        Args:
            line (str): The line to add to the paginated content.
            empty (bool): Indicates whether an empty line should be added at the end.
        """
        assert self.prefix

        remaining_words = None
        if len(line) > (max_chars := self.max_size - len(self.prefix) - 2) and len(line) > self.scale_to_size:
            line, remaining_words = self._split_remaining_words(line, max_chars)
            if len(line) > self.scale_to_size:
                LOGGER.debug("Could not continue to next page, truncating line.")
                line = line[: self.scale_to_size]

        # Check if we should start a new page or continue the line on the current one
        if self.max_lines is not None and self._linecount >= self.max_lines:
            LOGGER.debug("max_lines exceeded, creating new page.")
            self._new_page()
        elif self._count + len(line) + 1 > self.max_size and self._linecount > 0:
            LOGGER.debug("max_size exceeded on page with lines, creating new page.")
            self._new_page()

        self._linecount += 1

        self._count += len(line) + 1
        self._current_page.append(line)

        if empty:
            self._current_page.append("")
            self._count += 1

        # Start a new page if there were any overflow words
        if remaining_words:
            self._new_page()
            self.add_line(remaining_words)

    def _new_page(self) -> None:
        """
        Internal: start a new page for the paginator.

        This closes the current page and resets the counters for the new page's line count and
        character count.
        """
        assert self.prefix

        self._linecount = 0
        self._count = len(self.prefix) + 1
        self.close_page()

    def _split_remaining_words(self, line: str, max_chars: int) -> tuple[str, str | None]:
        """
        Internal: split a line into two strings -- reduced_words and remaining_words.

        reduced_words: the remaining words in `line`, after attempting to remove all words that
            exceed `max_chars` (rounding down to the nearest word boundary).

        remaining_words: the words in `line` which exceed `max_chars`. This value is None if
            no words could be split from `line`.

        If there are any remaining_words, an ellipses is appended to reduced_words and a
        continuation header is inserted before remaining_words to visually communicate the line
        continuation.

        Return a tuple in the format (reduced_words, remaining_words).
        """
        reduced_words = []
        remaining_words = []

        # "(Continued)" is used on a line by itself to indicate the continuation of last page
        continuation_header = "(Continued)\n-----------\n"
        reduced_char_count = 0
        is_full = False

        for word in line.split(" "):
            if not is_full:
                if len(word) + reduced_char_count <= max_chars:
                    reduced_words.append(word)
                    reduced_char_count += len(word) + 1
                else:
                    # If reduced_words is empty, we were unable to split the words across pages
                    if not reduced_words:
                        return line, None
                    is_full = True
                    remaining_words.append(word)
            else:
                remaining_words.append(word)

        return (
            " ".join(reduced_words) + "..." if remaining_words else "",
            continuation_header + " ".join(remaining_words) if remaining_words else None,
        )

    @classmethod
    async def paginate(
        cls,
        *,
        lines: list[str],
        ctx: Context | discord.Interaction,
        embed: discord.Embed,
        prefix: str = "",
        suffix: str = "",
        max_lines: int | None = None,
        max_size: int = 500,
        scale_to_size: int = 4000,
        empty: bool = True,
        restrict_to_user: discord.User | discord.Member | None = None,
        timeout: int = 300,
        footer_text: str | None = None,
        url: str | None = None,
        exception_on_empty_embed: bool = False,
        reply: bool = False,
        allowed_roles: Sequence[int] | None = None,
    ) -> discord.Message | None:
        """
        Use a paginator and set of reactions to provide pagination over a set of lines.

        The reactions are used to switch page, or to finish with pagination.

        When used, this will send a message using `ctx.send()` and apply a set of reactions to it. These reactions may
        be used to change page, or to remove pagination from the message.

        Pagination will also be removed automatically if no reaction is added for five minutes (300 seconds).

        The interaction will be limited to `restrict_to_user` (ctx.author by default) or
        to any user with a moderation role.

        Args:
            pagination_emojis (PaginationEmojis): The emojis used to navigate pages.
            lines (list[str]): A list of lines to be added to the paginated content.
            ctx (:obj:`discord.ext.commands.Context`): The context in which the pagination is needed.
            embed (:obj:`discord.Embed`): The embed that holds the content, it serves as the page.
            prefix (str): The prefix inserted to every page. e.g. three backticks.
            suffix (str): The suffix appended at the end of every page. e.g. three backticks.
            max_lines (int): The maximum amount of lines allowed in a page.
            max_size (int): The maximum amount of codepoints allowed in a page.
            scale_to_size (int): The maximum amount of characters a single line can scale up to.
            empty (bool): Indicates whether an empty line should be added to each provided line.
            restrict_to_user (:obj:`discord.User`): The user to whom interaction with the pages should be restricted.
            timeout (int): The timeout after which users cannot change pages anymore.
            footer_text (str): Text to be added as a footer for each page.
            url (str): The url to be set for the pagination embed.
            exception_on_empty_embed (bool): Indicates whether to raise an exception when no lines are provided.
            reply (bool): Indicates whether to send the page as a reply to the context's message.
            allowed_roles (Sequence[int]): A list of role ids that are allowed to change pages.

        Example:
        >>> embed = discord.Embed()
        >>> embed.set_author(name="Some Operation", url=url, icon_url=icon)
        >>> await LinePaginator.paginate(pagination_emojis, [line for line in lines], ctx, embed)
        """
        paginator = cls(prefix=prefix, suffix=suffix, max_size=max_size, max_lines=max_lines, scale_to_size=scale_to_size)
        current_page = 0

        if not restrict_to_user:
            restrict_to_user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author

        if not lines:
            if exception_on_empty_embed:
                LOGGER.exception("Pagination asked for empty lines iterable")
                raise EmptyPaginatorEmbedError("No lines to paginate")

            LOGGER.debug("No lines to add to paginator, adding '(nothing to display)' message")
            lines.append("*(nothing to display)*")

        for line in lines:
            try:
                paginator.add_line(line, empty=empty)
            except Exception:
                LOGGER.exception("Failed to add line to paginator: '%s'", line)
                raise  # Should propagate
            else:
                LOGGER.debug("Added line to paginator: '%s'", line)

        LOGGER.debug("Paginator created with %s pages", len(paginator.pages))

        embed.description = paginator.pages[current_page]

        reference = ctx.message if reply else None

        if len(paginator.pages) <= 1:
            if footer_text:
                embed.set_footer(text=footer_text)
                LOGGER.debug("Setting embed footer to '%s'", footer_text)

            if url:
                embed.url = url
                LOGGER.debug("Setting embed url to '%s'", url)

            LOGGER.debug("There's less than two pages, so we won't paginate - sending single page on its own")

            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(embed=embed)
                return None
            return await ctx.send(embeds=[embed], reference=reference)

        if footer_text:
            embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
        else:
            embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")
        LOGGER.debug("Setting embed footer to '%s'", embed.footer.text)

        if url:
            embed.url = url
            LOGGER.debug("Setting embed url to '%s'", url)

        LOGGER.debug("Sending first page to channel...")

        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=embed)
            message = await ctx.original_response()
        else:
            message = await ctx.send(embeds=[embed], reference=reference, wait=True)
            assert message

        LOGGER.debug("Adding emoji reactions to message...")

        pagination_emoji = [e.value for e in list(PaginationEmojis)]

        for emoji in pagination_emoji:
            # Add all the applicable emoji to the message
            LOGGER.debug("Adding reaction: %r", emoji)
            await message.add_reaction(emoji)

        check = partial(
            reaction_check,
            message_id=message.id,
            allowed_emoji=pagination_emoji,
            allowed_users=(restrict_to_user.id,),
            allowed_roles=allowed_roles,
        )

        while True:
            try:
                if isinstance(ctx, discord.Interaction):
                    reaction, user = await ctx.client.wait_for("reaction_add", timeout=timeout, check=check)
                else:
                    reaction, user = await ctx.bot.wait_for("reaction_add", timeout=timeout, check=check)
                LOGGER.debug("Got reaction: %s", reaction)
            except TimeoutError:
                LOGGER.debug("Timed out waiting for a reaction")
                break  # We're done, no reactions for the last 5 minutes

            if str(reaction.emoji) == PaginationEmojis.delete:
                LOGGER.debug("Got delete reaction")
                return await message.delete()
            if reaction.emoji in pagination_emoji:
                total_pages = len(paginator.pages)
                try:
                    await message.remove_reaction(reaction.emoji, user)
                except discord.HTTPException as e:
                    # Suppress if trying to act on an archived thread.
                    if e.code != 50083:
                        raise

                if reaction.emoji == PaginationEmojis.first:
                    current_page = 0
                    LOGGER.debug("Got first page reaction - changing to page 1/%s", total_pages)
                elif reaction.emoji == PaginationEmojis.last:
                    current_page = len(paginator.pages) - 1
                    LOGGER.debug("Got last page reaction - changing to page %s/%s", current_page + 1, total_pages)
                elif reaction.emoji == PaginationEmojis.left:
                    if current_page <= 0:
                        LOGGER.debug("Got previous page reaction, but we're on the first page - ignoring")
                        continue

                    current_page -= 1
                    LOGGER.debug("Got previous page reaction - changing to page %s/%s", current_page + 1, total_pages)
                elif reaction.emoji == PaginationEmojis.right:
                    if current_page >= len(paginator.pages) - 1:
                        LOGGER.debug("Got next page reaction, but we're on the last page - ignoring")
                        continue

                    current_page += 1
                    LOGGER.debug("Got next page reaction - changing to page %s/%s", current_page + 1, total_pages)

                embed.description = paginator.pages[current_page]

                if footer_text:
                    embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
                else:
                    embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")

                try:
                    await message.edit(embed=embed)
                except discord.HTTPException as e:
                    if e.code == 50083:
                        # Trying to act on an archived thread, just ignore and abort
                        break
                    raise

        LOGGER.debug("Ending pagination and clearing reactions.")
        with suppress(discord.NotFound):
            try:
                await message.clear_reactions()
            except discord.HTTPException as e:
                # Suppress if trying to act on an archived thread.
                if e.code != 50083:
                    raise


class LinePaginator(_LinePaginator):
    """
    A class that aids in paginating code blocks for Discord messages.

    See the super class's docs for more info.
    """

    @classmethod
    async def paginate(
        cls,
        *,
        lines: list[str],
        ctx: Context | discord.Interaction,
        embed: discord.Embed,
        prefix: str = "",
        suffix: str = "",
        max_lines: int | None = None,
        max_size: int = 500,
        scale_to_size: int = 4000,
        empty: bool = True,
        restrict_to_user: discord.User | None = None,
        timeout: int = 300,
        footer_text: str | None = None,
        url: str | None = None,
        exception_on_empty_embed: bool = False,
        reply: bool = False,
        allowed_roles: Sequence[int] | None = None,
        **kwargs,  # noqa: ANN003
    ) -> discord.Message | None:
        """
        Use a paginator and set of reactions to provide pagination over a set of lines.

        Acts as a wrapper for the super class' `paginate` method to provide the pagination emojis by default.

        Consult the super class's `paginate` method for detailed information.
        """
        return await super().paginate(
            lines=lines,
            ctx=ctx,
            embed=embed,
            prefix=prefix,
            suffix=suffix,
            max_lines=max_lines,
            max_size=max_size,
            scale_to_size=scale_to_size,
            empty=empty,
            restrict_to_user=restrict_to_user,
            timeout=timeout,
            footer_text=footer_text,
            url=url,
            exception_on_empty_embed=exception_on_empty_embed,
            reply=reply,
            allowed_roles=allowed_roles,
        )
