from enum import StrEnum
from typing import Literal, Self


class AnsiFormat(StrEnum):
    normal = "0"
    bold = "1"
    underline = "4"


AnsiFormatLiteral = Literal["normal", "bold", "underline"]


class AnsiColour(StrEnum):
    gray = "30"
    grey = "30"
    red = "31"
    green = "32"
    yellow = "33"
    blue = "34"
    pink = "35"
    cyan = "36"
    white = "37"


AnsiColourLiteral = Literal["gray", "grey", "red", "green", "yellow", "blue", "pink", "cyan", "white"]

AnsiColor = AnsiColour
AnsiColorLiteral = AnsiColourLiteral


class AnsiBackground(StrEnum):
    dark_blue = "40"
    orange = "41"
    marble_blue = "42"
    turqoise = "43"
    gray = "44"
    grey = "44"
    indigo = "45"
    light_gray = "46"
    light_grey = "46"
    white = "47"


AnsiBackgroundLiteral = Literal[
    "dark_blue", "orange", "marble_blue", "turqoise", "gray", "grey", "indigo", "light_gray", "light_grey", "white"
]

__all__ = ("AnsiBackground", "AnsiColor", "AnsiColour", "AnsiFormat", "AnsiString")


class AnsiString:
    __slots__ = ("__input_text", "_built_string")

    def __init__(self, input_text: str) -> None:
        self.__input_text = input_text  # format dunder only
        self._built_string = ""

    def __str__(self) -> str:
        return self.to_markdown()

    def __format__(self, __format_string: str, /) -> str:
        formatting, colour, background = __format_string.split("|")
        formatting = AnsiFormat[formatting] if formatting else AnsiFormat.normal
        colour = AnsiColour[colour] if colour else AnsiColour.grey
        background = AnsiBackground[background] if background else AnsiBackground.dark_blue

        self.clear()
        self.append(self.__input_text, formatting=formatting, colour=colour, background=background)
        return str(self)

    def clear(self) -> None:
        self._built_string = ""

    @property
    def text(self) -> str:
        return self._built_string

    @text.deleter
    def text(self) -> None:
        self._built_string = ""

    def to_markdown(self) -> str:
        return f"```ansi\n{self.text}\n```"

    def append(
        self,
        text: str,
        *,
        formatting: AnsiFormat | AnsiFormatLiteral | None = None,
        colour: AnsiColour | AnsiColor | AnsiColourLiteral | None = None,
        background: AnsiBackground | AnsiBackgroundLiteral | None = None,
        append_newline: bool = True,
    ) -> Self:
        ret = "\u001b["
        if formatting:
            formatting = AnsiFormat[formatting] if isinstance(formatting, str) else formatting
        else:
            formatting = AnsiFormat.normal
        ret += f"{formatting.value};"

        if background:
            background = AnsiBackground[background] if isinstance(background, str) else background
            ret += f"{background.value}"

        colour = (AnsiColour[colour] if isinstance(colour, str) else colour) if colour else AnsiColour.grey

        if background:
            ret += ";"
        ret += f"{colour.value}m"

        ret += f"{text}\u001b[0:0m{'\n' if append_newline else ''}"

        self._built_string += ret
        return self
