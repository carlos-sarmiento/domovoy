from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from domovoy.plugins.hass.types import EntityID, HassValue

EntityListenerCallbackEmpty = Callable[[], None | Awaitable[None]]


# Full Callback
class EntityListenerCallbackFull(Protocol):
    def __call__(
        self,
        *,
        entity_id: EntityID,
        attribute: str,
        old: HassValue,
        new: HassValue,
    ) -> None | Awaitable[None]: ...


# Single Parameter Callback
class EntityListenerCallbackWithEntityID(Protocol):
    def __call__(self, *, entity_id: EntityID) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithAttribute(Protocol):
    def __call__(self, *, attribute: str) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithOld(Protocol):
    def __call__(self, *, old: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithNew(Protocol):
    def __call__(self, *, new: HassValue) -> None | Awaitable[None]: ...


EntityListenerCallbackWithSingleParam = (
    EntityListenerCallbackWithEntityID
    | EntityListenerCallbackWithAttribute
    | EntityListenerCallbackWithOld
    | EntityListenerCallbackWithNew
)


# Two Parameters Callback
class EntityListenerCallbackWithEntityIDAndAttribute(Protocol):
    def __call__(self, *, entity_id: EntityID, attribute: str) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithEntityIDAndOld(Protocol):
    def __call__(self, *, entity_id: EntityID, old: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithEntityIDAndNew(Protocol):
    def __call__(self, *, entity_id: EntityID, new: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithAttributeAndOld(Protocol):
    def __call__(self, *, attribute: str, old: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithAttributeAndNew(Protocol):
    def __call__(self, *, attribute: str, new: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithOldAndNew(Protocol):
    def __call__(self, *, old: HassValue, new: HassValue) -> None | Awaitable[None]: ...


EntityListenerCallbackWithTwoParams = (
    EntityListenerCallbackWithEntityIDAndAttribute
    | EntityListenerCallbackWithEntityIDAndOld
    | EntityListenerCallbackWithEntityIDAndNew
    | EntityListenerCallbackWithAttributeAndOld
    | EntityListenerCallbackWithAttributeAndNew
    | EntityListenerCallbackWithOldAndNew
)


class EntityListenerCallbackWithAttributeAndOldAndNew(Protocol):
    def __call__(self, *, attribute: str, old: HassValue, new: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithEntityIDAndOldAndNew(Protocol):
    def __call__(self, *, entity_id: EntityID, old: HassValue, new: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithEntityIDAndAttributeAndNew(Protocol):
    def __call__(self, *, entity_id: EntityID, attribute: str, new: HassValue) -> None | Awaitable[None]: ...


class EntityListenerCallbackWithEntityIDAndAttributeAndOld(Protocol):
    def __call__(self, *, entity_id: EntityID, attribute: str, old: HassValue) -> None | Awaitable[None]: ...


EntityListenerCallbackWithThreeParams = (
    EntityListenerCallbackWithAttributeAndOldAndNew
    | EntityListenerCallbackWithEntityIDAndOldAndNew
    | EntityListenerCallbackWithEntityIDAndAttributeAndNew
    | EntityListenerCallbackWithEntityIDAndAttributeAndOld
)

EntityListenerCallback = (
    EntityListenerCallbackFull
    | EntityListenerCallbackWithThreeParams
    | EntityListenerCallbackWithTwoParams
    | EntityListenerCallbackWithSingleParam
    | EntityListenerCallbackEmpty
)
