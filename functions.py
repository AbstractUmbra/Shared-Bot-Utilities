"""Utilities for interaction with functions."""

import functools
import inspect
import logging
import types
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any, Concatenate, ParamSpec, TypeVar

LOGGER = logging.getLogger(__name__)

Argument = int | str
BoundArgs = OrderedDict[str, Any]
Decorator = Callable[[Callable], Callable]
ArgValGetter = Callable[[BoundArgs], Any]

P = ParamSpec("P")
T = TypeVar("T")


class GlobalNameConflictError(Exception):
    """Raised when there's a conflict between the globals used to resolve annotations of wrapped and its wrapper."""


def get_arg_value(name_or_pos: Argument, arguments: BoundArgs) -> Any:
    """
    Return a value from `arguments` based on a name or position.

    `arguments` is an ordered mapping of parameter names to argument values.

    Raise TypeError if `name_or_pos` isn't a str or int.
    Raise ValueError if `name_or_pos` does not match any argument.
    """
    if isinstance(name_or_pos, int):
        # Convert arguments to a tuple to make them indexable.
        arg_values = tuple(arguments.items())
        arg_pos = name_or_pos

        try:
            _, value = arg_values[arg_pos]
        except IndexError as err:
            msg = f"Argument position {arg_pos} is out of bounds."
            raise ValueError(msg) from err
        else:
            return value

    elif isinstance(name_or_pos, str):
        arg_name = name_or_pos
        try:
            return arguments[arg_name]
        except KeyError as err:
            msg = f"Argument {arg_name!r} doesn't exist."
            raise ValueError(msg) from err
    else:
        raise TypeError("'arg' must either be an int (positional index) or a str (keyword).")


def get_arg_value_wrapper(
    decorator_func: Callable[[ArgValGetter], Decorator],
    name_or_pos: Argument,
    func: Callable[[Any], Any] | None = None,
) -> Decorator:
    """
    Call `decorator_func` with the value of the arg at the given name/position.

    `decorator_func` must accept a callable as a parameter to which it will pass a mapping of
    parameter names to argument values of the function it's decorating.

    `func` is an optional callable which will return a new value given the argument's value.

    Return the decorator returned by `decorator_func`.
    """

    def wrapper(args: BoundArgs) -> Any:
        value = get_arg_value(name_or_pos, args)
        if func:
            value = func(value)
        return value

    return decorator_func(wrapper)


def get_bound_args(func: Callable, args: tuple, kwargs: dict[str, Any]) -> BoundArgs:
    """
    Bind `args` and `kwargs` to `func` and return a mapping of parameter names to argument values.

    Default parameter values are also set.
    """
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()

    return bound_args.arguments


def update_wrapper_globals(
    wrapper: Callable[Concatenate[P], T],
    wrapped: Callable[Concatenate[P], T],
    *,
    ignored_conflict_names: frozenset[str] = frozenset(),
) -> Callable[Concatenate[P], T]:
    """
    Update globals of `wrapper` with the globals from `wrapped`.

    For forwardrefs in command annotations discordpy uses the __global__ attribute of the function
    to resolve their values, with decorators that replace the function this breaks because they have
    their own globals.

    This function creates a new function functionally identical to `wrapper`, which has the globals replaced with
    a merge of `wrapped`s globals and the `wrapper`s globals.

    An exception will be raised in case `wrapper` and `wrapped` share a global name that is used by
    `wrapped`'s typehints and is not in `ignored_conflict_names`,
    as this can cause incorrect objects being used by discordpy's converters.
    """
    annotation_global_names = (
        ann.split(".", maxsplit=1)[0] for ann in wrapped.__annotations__.values() if isinstance(ann, str)
    )
    # Conflicting globals from both functions' modules that are also used in the wrapper and in wrapped's annotations.
    shared_globals = set(wrapper.__code__.co_names) & set(annotation_global_names)
    shared_globals &= set(wrapped.__globals__) & set(wrapper.__globals__) - ignored_conflict_names
    if shared_globals:
        msg = (
            f"wrapper and the wrapped function share the following "
            f"global names used by annotations: {', '.join(shared_globals)}. Resolve the conflicts or add "
            f"the name to the `ignored_conflict_names` set to suppress this error if this is intentional."
        )
        raise GlobalNameConflictError(msg)

    new_globals = wrapper.__globals__.copy()
    new_globals.update((k, v) for k, v in wrapped.__globals__.items() if k not in wrapper.__code__.co_names)
    return types.FunctionType(
        code=wrapper.__code__,
        globals=new_globals,
        name=wrapper.__name__,
        argdefs=wrapper.__defaults__,
        closure=wrapper.__closure__,
    )


def command_wraps[**P, T](
    wrapped: Callable[Concatenate[P], T],
    assigned: Sequence[str] = functools.WRAPPER_ASSIGNMENTS,
    updated: Sequence[str] = functools.WRAPPER_UPDATES,
    *,
    ignored_conflict_names: frozenset[str] = frozenset(),
) -> Callable[[Callable[Concatenate[P], T]], Callable[Concatenate[P], T]]:
    """Update the decorated function to look like `wrapped` and update globals for discordpy forwardref evaluation."""

    def decorator(
        wrapper: Callable[Concatenate[P], T],
    ) -> Callable[Concatenate[P], T]:
        return functools.update_wrapper(
            update_wrapper_globals(wrapper, wrapped, ignored_conflict_names=ignored_conflict_names),
            wrapped,
            assigned,
            updated,
        )

    return decorator
