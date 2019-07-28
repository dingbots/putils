"""
Decorator to deal with the very annoying and grossly incomplete
ComponentResource boilerplate.
"""

import pulumi
import asyncio

from .paio import FauxOutput, task, unwrap


class Component(pulumi.ComponentResource):
    def __init_subclass__(cls, namespace=None, outputs=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if namespace is not None:
            cls.__namespace__ = namespace
        elif not hasattr(cls, '__namespace__'):
            cls.__namespace__ = f"{cls.__module__}:{cls.__qualname__}".replace('.', ':')

        if outputs is not None:
            cls.__outputs__ = outputs
        elif not hasattr(cls, '__outputs__'):
            cls.__outputs__ = []

    def __init__(self, __name__, *pargs, __opts__=None, **kwargs):
        super().__init__(self.__namespace__, __name__, None, __opts__)
        futures = {}
        # Build out the declared outputs so they're available immediately
        for name in self.__outputs__:
            # FIXME: Use real Outputs instead of FauxOutputs
            output, futures[name] = FauxOutput.from_nothing()
            setattr(self, name, output)
        if asyncio.iscoroutine(self.set_up):
            self._inittask(futures, __name__, *pargs, __opts__=__opts__, **kwargs)
        else:
            try:
                outs = self.set_up(__name__, *pargs, __opts__=__opts__, **kwargs)
            except Exception as e:
                for f in futures.values():
                    f.set_exception(e)
                raise
            else:
                self._process_outs(outs, futures)

    @task
    async def _inittask(self, futures, *pargs, **kwargs):
        # Wraps up the initialization function and marshalls the data around
        try:
            # Call the initializer
            outs = await unwrap(self.set_up(*pargs, **kwargs))
        except Exception as e:
            # Forward the exception to the futures, so they don't hang
            for f in futures.values():
                f.set_exception(e)
            raise
        else:
            self._process_outs(outs, futures)

    def _process_outs(self, outs, futures=None):
        if outs is None:
            outs = {}
        self.register_outputs(outs)
        for name, value in outs.items():
            if futures is not None and name in futures:
                futures[name].set_result(value)
            else:
                setattr(self, name, value)

    def set_up(self, *pargs, **kwargs):
        pass


def component(namespace=None, outputs=()):
    """
    Makes the given callable a component, with much less boilerplate.

    If no namespace is given, uses the module and function names

    @component('pkg:MyResource')
    def MyResource(self, name, ..., __opts__):
        ...
        return {...outputs}
    """
    def _(func):
        nonlocal namespace
        if namespace is None:
            namespace = f"{func.__module__}:{func.__qualname__}".replace('.', ':')

        klass = type(func.__name__, (Component,), {
            '__doc__': func.__doc__,
            '__module__': func.__module__,
            '__qualname__': func.__qualname__,
            'set_up': func,
            '__namespace__': namespace,
            '__outputs__': outputs,
        })
        return klass

    return _
