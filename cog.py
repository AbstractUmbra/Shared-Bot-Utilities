import inspect
import logging
from collections.abc import Callable
from typing import (
    Any,
    Literal,
    NamedTuple,
    TypeVar,
)

from aiohttp import web
from aiohttp.web import Request
from discord.ext import commands
from discord.utils import MISSING

__all__: tuple[str, ...] = (
    "BaseCog",
    "Request",
    "WebserverCog",
    "route",
)

FuncT = TypeVar("FuncT", bound="Callable[..., Any]")
BotT = TypeVar("BotT", bound="commands.Bot")


class Route(NamedTuple):
    name: str
    method: str
    func: Callable[..., Any]


def route(method: Literal["get", "post", "put", "patch", "delete"], request_path: str) -> Callable[[FuncT], FuncT]:
    def decorator(func: FuncT) -> FuncT:
        actual = func
        if isinstance(actual, staticmethod):
            actual = actual.__func__
        if not inspect.iscoroutinefunction(actual):
            raise TypeError("Route function must be a coroutine.")

        actual.__ipc_route_path__ = request_path
        actual.__ipc_method__ = method
        return func

    return decorator


class _BaseWebserver:
    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def __init__(self) -> None:
        self.routes: list[Route] = []

        self.app: web.Application = web.Application()
        self._runner = web.AppRunner(self.app)
        self._webserver: web.TCPSite | None = None

        for attr in (getattr(self, x, None) for x in dir(self)):
            if attr is None:
                continue
            if (name := getattr(attr, "__ipc_route_path__", None)) is not None:
                route: str = attr.__ipc_method__
                self.routes.append(Route(func=attr, name=name, method=route))

        self.app.add_routes([web.route(x.method, x.name, x.func) for x in self.routes])

    async def start(self, *, host: str = "localhost", port: int) -> None:
        self.logger.debug("Starting %s runner.", self.__class__.__name__)
        await self._runner.setup()
        self.logger.debug("Starting %s webserver.", self.__class__.__name__)
        self._webserver = web.TCPSite(self._runner, host=host, port=port)
        await self._webserver.start()

    async def close(self) -> None:
        self.logger.debug("Cleaning up after %s.", self.__class__.__name__)
        await self._runner.cleanup()
        if self._webserver:
            self.logger.debug("Closing %s webserver.", self.__class__.__name__)
            await self._webserver.stop()


class BaseCog[BotT: "commands.Bot"](commands.Cog):
    def __init__(self, bot: BotT, /) -> None:
        self.bot: BotT = bot

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class WebserverCog(BaseCog[BotT], _BaseWebserver):
    """A webserver cog that implements cog_load and cog_unload to set up the webserver.

    .. code-block:: python3

        from aiohttp import web
        from discord.ext.duck import webserver


        class MyWSCog(webserver.WebserverCog, port=8080):
            @webserver.route("GET", "/stats")
            async def stats(self, request: web.Request):
                return web.json_response({"stats": {"servers": 1e9}})


        # then, somewhere:
        await bot.add_cog(MyWSCog())
    """

    __runner_port__: int
    __runner_host__: str

    def __init_subclass__(cls, *, auto_start: bool = True, host: str = "127.0.0.1", port: int = MISSING) -> None:
        if auto_start is True and port is MISSING:
            message = (
                f"A port must be provided when auto_start=True. For example:\n"
                f"\nclass {cls.__name__}(WebserverCog, port=8080):\n    ...\n"
                f"\nclass {cls.__name__}(WebserverCog, auto_start=False):"
                '\n    """You are responsible for calling (async) self.start(port=...) when using this."""\n\n'
            )
            raise RuntimeError(message)
        cls.__runner_port__ = port
        cls.__runner_host__ = host
        return super().__init_subclass__()

    async def cog_load(self) -> None:
        await self.start(host=self.__runner_host__, port=self.__runner_port__)
        return await super().cog_load()

    async def cog_unload(self) -> None:
        await self.close()
        return await super().cog_unload()
