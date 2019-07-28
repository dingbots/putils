"""
Pulumi/asyncio helpers.

Most of this just deals with annoying boilerplate (@task, @background), but
@outputish and FauxOutput transform coroutines into Pulumi Output-like thing.
"""

import pulumi
import inspect
import asyncio
import functools
import traceback


__all__ = 'task', 'background', 'outputish', 'FauxOutput'


def mkfuture(val):
    """
    Wrap the given value in a future (turn into a task).

    Intelligentally handles awaitables vs not.

    Note: Does not perform error handling for the task.
    """
    if inspect.isawaitable(val):
        return asyncio.ensure_future(val)
    else:
        f = asyncio.get_event_loop().create_future()
        f.set_result(val)
        return f


async def unwrap(value):
    """
    Resolve all the awaitables, returing a simple value.
    """
    # This is to make sure awaitables boxing awaitables get handled.
    # This shouldn't happen in proper programs, but async can be hard.
    while inspect.isawaitable(value):
        value = await value
        if __debug__ and inspect.isawaitable(value):
            pulumi.warn(f"Programming error: nested awaitables: {value}")
    return value


def task(func):
    """
    Decorator to turn coroutines into tasks.

    Will also log errors, so failures don't go unreported.
    """
    async def runner(*pargs, **kwargs):
        try:
            return await func(*pargs, **kwargs)
        except Exception:
            traceback.print_exc()
            pulumi.error(f"Error in {func}")
            raise

    @functools.wraps(func)
    def wrapper(*pargs, **kwargs):
        return asyncio.create_task(runner(*pargs, **kwargs))

    return wrapper


def background(func):
    """
    Turns a synchronous function into an async one by running it in a
    background thread.
    """
    @functools.wraps(func)
    def wrapper(*pargs, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, functools.partial(func, *pargs, **kwargs))

    return wrapper


def outputish(func):
    """
    Decorator to produce FauxOutputs on call
    """
    @functools.wraps(func)
    def wrapper(*pargs, **kwargs):
        return FauxOutput(func(*pargs, **kwargs))

    return wrapper


class FauxOutput:
    """
    Acts like an Output-like for plain coroutines.
    """
    def __init__(self, coro):
        self._value = mkfuture(coro)

    @classmethod
    def from_nothing(cls):
        """
        Return a FauxOutput and the future that drives it
        """
        fut = asyncio.get_event_loop().create_future()
        return cls(fut), fut

    @classmethod
    def from_value(cls, value):
        """
        Return a FauxOutput from a simple value
        """
        return cls(value)  # __init__ calls mkfuture, which handles this for us

    @outputish
    async def __getitem__(self, key):
        """
        Shortcut to index the eventual value.
        """
        return (await self._value)[key]

    @outputish
    async def __getattr__(self, name):
        """
        Shortcut to get an attribute from the eventual value.
        """
        return getattr(await self._value, name)

    @outputish
    async def apply(self, func):
        """
        Eventually call the given function with the eventual value.
        """
        value = await unwrap(self._value)
        rv = func(value)
        return await unwrap(rv)

    def __await__(self):
        return self._value.__await__()

    def future(self):
        """
        Get an awaitable for the boxed value.
        """
        return self._value
