"""Bounded structured task-proposal contract for the integrated demonstrator."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from .governance_contract_v2 import ContractModel


IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ActionType(StrEnum):
    MOVE = "MOVE"
    PICK = "PICK"
    PLACE = "PLACE"
    WAIT = "WAIT"
    STOP = "STOP"
    INSPECT = "INSPECT"


class ActionStepV2(ContractModel):
    action: ActionType
    object_id: str | None = None
    source_id: str | None = None
    destination_id: str | None = None
    duration_ms: int | None = Field(default=None, ge=1, le=60_000)

    @field_validator("object_id", "source_id", "destination_id")
    @classmethod
    def identifiers_are_canonical(cls, value: str | None) -> str | None:
        if value is not None and not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("entity identifiers must use lower_snake_case")
        return value

    @model_validator(mode="after")
    def action_has_required_fields(self) -> "ActionStepV2":
        if self.action is ActionType.MOVE:
            required = (self.object_id, self.source_id, self.destination_id)
            if any(value is None for value in required):
                raise ValueError("MOVE requires object_id, source_id, and destination_id")
            if self.duration_ms is not None:
                raise ValueError("MOVE cannot define duration_ms")
        elif self.action is ActionType.PICK:
            if self.object_id is None or self.source_id is None:
                raise ValueError("PICK requires object_id and source_id")
            if self.destination_id is not None or self.duration_ms is not None:
                raise ValueError("PICK cannot define destination_id or duration_ms")
        elif self.action is ActionType.PLACE:
            if self.object_id is None or self.destination_id is None:
                raise ValueError("PLACE requires object_id and destination_id")
            if self.source_id is not None or self.duration_ms is not None:
                raise ValueError("PLACE cannot define source_id or duration_ms")
        elif self.action is ActionType.WAIT:
            if self.duration_ms is None:
                raise ValueError("WAIT requires duration_ms")
            if any(
                value is not None
                for value in (self.object_id, self.source_id, self.destination_id)
            ):
                raise ValueError("WAIT cannot define object or location fields")
        elif self.action is ActionType.STOP:
            if any(
                value is not None
                for value in (
                    self.object_id,
                    self.source_id,
                    self.destination_id,
                    self.duration_ms,
                )
            ):
                raise ValueError("STOP cannot define object, location, or duration fields")
        elif self.action is ActionType.INSPECT:
            if self.object_id is None:
                raise ValueError("INSPECT requires object_id")
            if self.destination_id is not None or self.duration_ms is not None:
                raise ValueError("INSPECT cannot define destination_id or duration_ms")
        return self


class StructuredTaskProposalV2(ContractModel):
    actions: tuple[ActionStepV2, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def action_sequence_is_bounded(self) -> "StructuredTaskProposalV2":
        stop_indexes = [
            index
            for index, action in enumerate(self.actions)
            if action.action is ActionType.STOP
        ]
        if stop_indexes and stop_indexes[-1] != len(self.actions) - 1:
            raise ValueError("STOP must be the final action")
        if len(stop_indexes) > 1:
            raise ValueError("proposal cannot contain multiple STOP actions")
        return self
