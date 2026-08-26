"""Bounded structured task-proposal contract for the integrated demonstrator."""

from __future__ import annotations

import json
import re
from enum import StrEnum

from pydantic import Field, ValidationError, field_validator, model_validator

from .governance_contract_v2 import ContractModel, GateStatus


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


class ProposalStructuralAssessmentV2(ContractModel):
    parse_status: GateStatus
    json_status: GateStatus
    schema_status: GateStatus
    proposal: StructuredTaskProposalV2 | None
    reason_code: str | None = None

    @model_validator(mode="after")
    def proposal_requires_all_structural_gates(
        self,
    ) -> "ProposalStructuralAssessmentV2":
        all_pass = all(
            status is GateStatus.PASSED
            for status in (
                self.parse_status,
                self.json_status,
                self.schema_status,
            )
        )
        if all_pass != (self.proposal is not None):
            raise ValueError("proposal must exist exactly when all structural gates pass")
        if all_pass and self.reason_code is not None:
            raise ValueError("successful structural assessment cannot have a reason")
        if not all_pass and self.reason_code is None:
            raise ValueError("failed structural assessment requires a reason")
        return self


def assess_structured_proposal(
    raw_text: str | None,
) -> ProposalStructuralAssessmentV2:
    """Apply the one shared parse/JSON/schema contract used by routing and governance."""

    if raw_text is None or not raw_text.strip():
        return ProposalStructuralAssessmentV2(
            parse_status=GateStatus.FAILED,
            json_status=GateStatus.NOT_ASSESSABLE,
            schema_status=GateStatus.NOT_ASSESSABLE,
            proposal=None,
            reason_code="PROVIDER_RESPONSE_EMPTY",
        )
    try:
        payload = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return ProposalStructuralAssessmentV2(
            parse_status=GateStatus.FAILED,
            json_status=GateStatus.FAILED,
            schema_status=GateStatus.NOT_ASSESSABLE,
            proposal=None,
            reason_code="JSON_PARSE_FAILED",
        )
    if not isinstance(payload, dict):
        return ProposalStructuralAssessmentV2(
            parse_status=GateStatus.PASSED,
            json_status=GateStatus.FAILED,
            schema_status=GateStatus.NOT_ASSESSABLE,
            proposal=None,
            reason_code="JSON_ROOT_NOT_OBJECT",
        )
    try:
        proposal = StructuredTaskProposalV2.model_validate(payload)
    except ValidationError:
        return ProposalStructuralAssessmentV2(
            parse_status=GateStatus.PASSED,
            json_status=GateStatus.PASSED,
            schema_status=GateStatus.FAILED,
            proposal=None,
            reason_code="PROPOSAL_SCHEMA_INVALID",
        )
    return ProposalStructuralAssessmentV2(
        parse_status=GateStatus.PASSED,
        json_status=GateStatus.PASSED,
        schema_status=GateStatus.PASSED,
        proposal=proposal,
    )
