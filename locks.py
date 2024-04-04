from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine, Hashable
from functools import partial
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar
from weakref import WeakValueDictionary

from .errors import LockedResourceError
from .functions import Argument, BoundArgs, command_wraps, get_arg_value_wrapper, get_bound_args

if TYPE_CHECKING:
    from types import TracebackType

LOGGER = logging.getLogger(__name__)
__lock_dicts = defaultdict(WeakValueDictionary)

_IdCallableReturn = Hashable | Awaitable[Hashable]
_IdCallable = Callable[[BoundArgs], _IdCallableReturn]
ResourceId = Hashable | _IdCallable

C = TypeVar("C")
P = ParamSpec("P")
T = TypeVar("T")


class SharedEvent:
    """
    Context manager managing an internal event exposed through the wait coro.

    While any code is executing in this context manager, the underlying event will not be set;
    when all of the holders finish the event will be set.
    """

    def __init__(self) -> None:
        self._active_count = 0
        self._event = asyncio.Event()
        self._event.set()

    def __enter__(self) -> None:
        """Increment the count of the active holders and clear the internal event."""
        self._active_count += 1
        self._event.clear()

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Decrement the count of the active holders; if 0 is reached set the internal event."""
        self._active_count -= 1
        if not self._active_count:
            self._event.set()

    async def wait(self) -> None:
        """Wait for all active holders to exit."""
        await self._event.wait()


def lock(
    namespace: Hashable,
    resource_id: ResourceId,
    *,
    raise_error: bool = False,
    wait: bool = False,
) -> Callable:
    """
    Turn the decorated coroutine function into a mutually exclusive operation on a `resource_id`.

    If `wait` is True, wait until the lock becomes available. Otherwise, if any other mutually
    exclusive function currently holds the lock for a resource, do not run the decorated function
    and return None.

    If `raise_error` is True, raise `LockedResourceError` if the lock cannot be acquired.

    `namespace` is an identifier used to prevent collisions among resource IDs.

    `resource_id` identifies a resource on which to perform a mutually exclusive operation.
    It may also be a callable or awaitable which will return the resource ID given an ordered
    mapping of the parameters' names to arguments' values.

    If decorating a command, this decorator must go before (below) the `command` decorator.
    """

    def decorator(
        func: Callable[Concatenate[P], Coroutine[Any, Any, T]],
    ) -> Callable[Concatenate[P], Coroutine[Any, Any, T | None]]:
        name = func.__name__

        @command_wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            LOGGER.debug("%s: mutually exclusive decorator called", name)

            if callable(resource_id):
                LOGGER.debug("%s: binding args to signature", name)
                bound_args = get_bound_args(func, args, kwargs)

                LOGGER.debug("%s: calling the given callable to get the resource ID", name)
                id_ = resource_id(bound_args)

                if inspect.isawaitable(id_):
                    LOGGER.debug("%s: awaiting to get resource ID", name)
                    id_ = await id_
            else:
                id_ = resource_id

            LOGGER.debug("%s: getting the lock object for resource %r:%r", name, namespace, id_)

            # Get the lock for the ID. Create a lock if one doesn't exist yet.
            locks = __lock_dicts[namespace]
            lock_ = locks.setdefault(id_, asyncio.Lock())

            # It's safe to check an asyncio.Lock is free before acquiring it because:
            #   1. Synchronous code like `if not lock_.locked()` does not yield execution
            #   2. `asyncio.Lock.acquire()` does not internally await anything if the lock is free
            #   3. awaits only yield execution to the event loop at actual I/O boundaries
            if wait or not lock_.locked():
                LOGGER.debug("%s: acquiring lock for resource %r:%r...", name, namespace, id_)
                async with lock_:
                    return await func(*args, **kwargs)
            else:
                LOGGER.info("%s: aborted because resource %r:%r is locked", name, namespace, id_)
                if raise_error:
                    raise LockedResourceError(str(namespace), id_)
                return None

        return wrapper

    return decorator


def lock_arg(
    namespace: Hashable,
    name_or_pos: Argument,
    func: Callable[[Any], _IdCallableReturn] | None = None,
    *,
    raise_error: bool = False,
    wait: bool = False,
) -> Callable:
    """
    Apply the `lock` decorator using the value of the arg at the given name/position as the ID.

    `func` is an optional callable or awaitable which will return the ID given the argument value.
    See `lock` docs for more information.
    """
    decorator_func = partial(lock, namespace, raise_error=raise_error, wait=wait)
    return get_arg_value_wrapper(decorator_func, name_or_pos, func)
