"""Explicit FastAPI policies, separate from ordinary route dependencies.

Policies see the original request. They describe an operation, not a synthetic
HTTP method, and must raise to deny access. Their dependency cache and yield
lifetimes belong to this request's authorization context. Ordinary route
dependencies are never copied into this graph; share principal/client objects
through request.state when both graphs need them.
"""

from __future__ import annotations

import asyncio
import inspect
from contextlib import AsyncExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import replace
from functools import partial
from typing import Any, Callable, cast

import anyio
from fastapi import Request
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import get_dependant, get_parameterless_sub_dependant, solve_dependencies
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends


current_authorization: ContextVar[AuthorizationContext | None] = ContextVar(
    "safrs_fastapi_authorization", default=None
)


class AuthorizationContext:
    def __init__(self, request: Request, app: Any, limiter: anyio.CapacityLimiter) -> None:
        self.request = request
        self.app = app
        self.limiter = limiter
        self.stack = AsyncExitStack()
        self.cache: dict[Any, Any] = {}
        self.calls: dict[Any, Callable[..., Any]] = {}
        self.checked_operations: set[tuple[type[Any], str]] = set()
        self.checked_resources: set[tuple[type[Any], int]] = set()

    def run(self, function: Callable[..., Any], *args: Any) -> Any:
        """Bridge sync SAFRS handlers to the application's event loop."""
        try:
            return anyio.from_thread.run(function, *args)
        except RuntimeError as exc:
            if str(exc) not in {
                "This function can only be run from an AnyIO worker thread",
                "Not running inside an AnyIO worker thread, and no event loop token was provided",
            }:
                raise
            # Support trusted direct handler calls outside an ASGI request.
            return asyncio.run(function(*args))

    def _adapt(self, dependant: Dependant) -> Dependant:
        """Keep native parameter/Security resolution with a separate worker pool.

        Sync handlers already hold a default worker token. Scheduling their
        policies on that same saturated pool would deadlock. No global limiter
        is changed, and async policies keep their application-loop affinity.
        """
        call = dependant.call
        override = self.app.dependency_overrides.get(call)
        if override is not None:
            use_cache = dependant.use_cache
            dependant = get_dependant(
                path=dependant.path or "",
                call=override,
                name=dependant.name,
                parent_oauth_scopes=dependant.oauth_scopes,
                scope=dependant.scope,
            )
            dependant.use_cache = use_cache
            call = override
        children = [self._adapt(child) for child in dependant.dependencies]
        if call is None or dependant.is_coroutine_callable or dependant.is_async_gen_callable:
            return replace(dependant, dependencies=children)
        if call not in self.calls:
            if dependant.is_gen_callable:
                self.calls[call] = self._generator(call)
            else:
                async def invoke(_call: Callable[..., Any] = cast(Callable[..., Any], call), **kwargs: Any) -> Any:
                    return await anyio.to_thread.run_sync(partial(_call, **kwargs), limiter=self.limiter)
                self.calls[call] = invoke
        return replace(dependant, call=self.calls[call], dependencies=children)

    def _generator(self, call: Callable[..., Any]) -> Callable[..., Any]:
        async def invoke(**kwargs: Any) -> Any:
            manager = contextmanager(call)(**kwargs)
            value = await anyio.to_thread.run_sync(manager.__enter__, limiter=self.limiter)
            try:
                yield value
            except BaseException as exc:
                with anyio.CancelScope(shield=True):
                    suppressed = await anyio.to_thread.run_sync(
                        partial(manager.__exit__, type(exc), exc, exc.__traceback__), limiter=self.limiter
                    )
                if not suppressed:
                    raise
            else:
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(
                        partial(manager.__exit__, None, None, None), limiter=self.limiter
                    )
        return invoke

    async def check(self, dependencies: list[Depends]) -> None:
        path = getattr(self.request.scope.get("route"), "path_format", self.request.url.path)
        dependant = Dependant(dependencies=[
            self._adapt(get_parameterless_sub_dependant(depends=dependency, path=path))
            for dependency in dependencies
        ])
        # Use the original Request, including its cached body, state and stream.
        # Only the solver's stacks are redirected, and restored before returning.
        keys = ("fastapi_inner_astack", "fastapi_function_astack")
        original = {key: self.request.scope.get(key) for key in keys}
        for key in keys:
            self.request.scope[key] = self.stack
        try:
            body = await self.request.json() if getattr(self.request, "_body", b"") else None
            solved = await solve_dependencies(
                request=self.request,
                dependant=dependant,
                body=body,
                dependency_cache=self.cache,
                async_exit_stack=self.stack,
                embed_body_fields=False,
            )
            if solved.errors:
                raise RequestValidationError(solved.errors)
        finally:
            for key, value in original.items():
                if value is None:
                    self.request.scope.pop(key, None)
                else:
                    self.request.scope[key] = value

    async def callback(self, result: Any) -> Any:
        return await result

    def authorize_response(self, function: Callable[..., Any], model: type[Any], instance: Any) -> None:
        allowed = function(model, instance, self.request)
        if inspect.isawaitable(allowed):
            allowed = self.run(self.callback, allowed)
        if allowed is False:
            from fastapi import HTTPException
            raise HTTPException(403, "Response resource is not authorized")
