from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
Handler = Callable[[BaseModel, dict[str, Any]], Awaitable[Any]]


class RegisteredAction(Generic[InputT]):
    def __init__(self, input_model: type[InputT], handler: Handler) -> None:
        self.input_model = input_model
        self.handler = handler

    def validate(self, raw: Mapping[str, Any]) -> InputT:
        return self.input_model.model_validate(dict(raw))

    async def execute(self, validated: InputT, state: dict[str, Any]) -> Any:
        return await self.handler(validated, state)


@dataclass(frozen=True)
class PreparedAction:
    name: str
    action: RegisteredAction[BaseModel]
    validated: BaseModel


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, RegisteredAction[BaseModel]] = {}

    def register(
        self,
        name: str,
        input_model: type[InputT],
        handler: Callable[[InputT, dict[str, Any]], Awaitable[Any]],
    ) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("action name must not be blank")
        if normalized in self._actions:
            raise ValueError(f"action already registered: {normalized}")
        registered = RegisteredAction(input_model, cast(Handler, handler))
        self._actions[normalized] = cast(RegisteredAction[BaseModel], registered)

    def resolve(self, name: str) -> RegisteredAction[BaseModel]:
        normalized = name.strip().lower()
        try:
            return self._actions[normalized]
        except KeyError as exc:
            raise LookupError(f"unknown action: {normalized}") from exc

    def prepare(self, name: str, raw: Mapping[str, Any]) -> PreparedAction:
        action = self.resolve(name)
        return PreparedAction(name.strip().lower(), action, action.validate(raw))

    async def execute_prepared(
        self, prepared: PreparedAction, state: dict[str, Any]
    ) -> Any:
        return await prepared.action.execute(prepared.validated, state)

    async def dispatch(
        self, name: str, raw: Mapping[str, Any], state: dict[str, Any]
    ) -> Any:
        return await self.execute_prepared(self.prepare(name, raw), state)
