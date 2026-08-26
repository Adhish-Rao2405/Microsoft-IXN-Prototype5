"""Deterministic manufacturing command and proposal evaluation for A2.2."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from .governance_contract_v2 import ContractModel, GateStatus, PlanSemanticStatus
from .task_proposal_v2 import (
    IDENTIFIER_PATTERN,
    ActionStepV2,
    ActionType,
    StructuredTaskProposalV2,
)


REASON_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class ActionAliasRuleV2(ContractModel):
    action: ActionType
    aliases: tuple[str, ...] = Field(min_length=1)


class EntityAliasRuleV2(ContractModel):
    entity_id: str
    aliases: tuple[str, ...] = Field(min_length=1)

    @field_validator("entity_id")
    @classmethod
    def entity_id_is_canonical(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("entity identifiers must use lower_snake_case")
        return value


class LocationAliasRuleV2(EntityAliasRuleV2):
    restricted: bool = False


class SafetyPhraseRuleV2(ContractModel):
    reason_code: str
    phrases: tuple[str, ...] = Field(min_length=1)

    @field_validator("reason_code")
    @classmethod
    def reason_code_is_valid(cls, value: str) -> str:
        if not REASON_PATTERN.fullmatch(value):
            raise ValueError("safety reason codes must use upper snake case")
        return value


class AuthorityRuleV2(ContractModel):
    role: str
    allowed_actions: tuple[ActionType, ...]


class ManufacturingPolicyConfigV2(ContractModel):
    policy_id: str
    policy_version: str
    scope_boundary: str
    action_aliases: tuple[ActionAliasRuleV2, ...]
    objects: tuple[EntityAliasRuleV2, ...]
    locations: tuple[LocationAliasRuleV2, ...]
    ambiguous_phrases: tuple[str, ...]
    safety_phrase_rules: tuple[SafetyPhraseRuleV2, ...]
    authority_rules: tuple[AuthorityRuleV2, ...]

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> "ManufacturingPolicyConfigV2":
        _require_unique(
            [rule.action.value for rule in self.action_aliases], "action aliases"
        )
        _require_unique([rule.entity_id for rule in self.objects], "object identifiers")
        _require_unique(
            [rule.entity_id for rule in self.locations], "location identifiers"
        )
        _require_unique([rule.role for rule in self.authority_rules], "authority roles")
        _require_unique(
            [rule.reason_code for rule in self.safety_phrase_rules],
            "safety reason codes",
        )
        return self


class LoadedManufacturingPolicyV2(ContractModel):
    config: ManufacturingPolicyConfigV2
    sha256: str


class SceneObjectStateV2(ContractModel):
    object_id: str
    location_id: str

    @field_validator("object_id", "location_id")
    @classmethod
    def identifiers_are_canonical(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("scene identifiers must use lower_snake_case")
        return value


class ManufacturingSceneStateV2(ContractModel):
    scene_id: str
    state_version: str
    objects: tuple[SceneObjectStateV2, ...]
    human_obstruction: bool = False
    safety_interlock_enabled: bool = True

    @model_validator(mode="after")
    def object_identifiers_are_unique(self) -> "ManufacturingSceneStateV2":
        _require_unique([item.object_id for item in self.objects], "scene objects")
        return self

    def object_location(self, object_id: str | None) -> str | None:
        if object_id is None:
            return None
        return next(
            (
                item.location_id
                for item in self.objects
                if item.object_id == object_id
            ),
            None,
        )


class RequesterContextV2(ContractModel):
    requester_id: str
    role: str

    @field_validator("requester_id", "role")
    @classmethod
    def identifiers_are_canonical(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("requester identifiers must use lower_snake_case")
        return value


class CommandInterpretationV2(ContractModel):
    action: ActionType | None
    object_id: str | None
    source_id: str | None
    destination_id: str | None
    duration_ms: int | None = Field(default=None, ge=1, le=60_000)
    ambiguity_reason_codes: tuple[str, ...] = ()
    safety_reason_codes: tuple[str, ...] = ()


class ManufacturingPolicyEvaluationV2(ContractModel):
    interpretation: CommandInterpretationV2
    plan_semantic_status: PlanSemanticStatus
    semantic_reason_codes: tuple[str, ...]
    ambiguity_status: GateStatus
    ambiguity_reason_codes: tuple[str, ...]
    safety_status: GateStatus
    safety_reason_codes: tuple[str, ...]
    authority_status: GateStatus
    authority_reason_codes: tuple[str, ...]


def load_manufacturing_policy(path: Path) -> LoadedManufacturingPolicyV2:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    return LoadedManufacturingPolicyV2(
        config=ManufacturingPolicyConfigV2.model_validate(payload),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def interpret_manufacturing_command(
    command: str,
    scene: ManufacturingSceneStateV2,
    policy: ManufacturingPolicyConfigV2,
) -> CommandInterpretationV2:
    normalised = _normalise(command)
    action = _resolve_action(normalised, policy)
    object_id = _resolve_entity(normalised, policy.objects)
    source_id = _resolve_location(normalised, policy.locations, source=True)
    destination_id = _resolve_location(normalised, policy.locations, source=False)
    duration_ms = _resolve_duration_ms(normalised) if action is ActionType.WAIT else None

    if source_id is None:
        source_id = scene.object_location(object_id)

    safety_reasons = _command_safety_reasons(normalised, policy)
    ambiguity_reasons: list[str] = []
    if not safety_reasons:
        if action is None:
            ambiguity_reasons.append("ACTION_UNRESOLVED")
        elif action in (
            ActionType.MOVE,
            ActionType.PICK,
            ActionType.PLACE,
            ActionType.INSPECT,
        ):
            if object_id is None:
                ambiguity_reasons.append("OBJECT_UNRESOLVED")
            if action is ActionType.MOVE and destination_id is None:
                ambiguity_reasons.append("DESTINATION_UNRESOLVED")
            if action is ActionType.PLACE and destination_id is None:
                ambiguity_reasons.append("DESTINATION_UNRESOLVED")
        elif action is ActionType.WAIT and duration_ms is None:
            ambiguity_reasons.append("DURATION_UNRESOLVED")
        if any(_contains_phrase(normalised, phrase) for phrase in policy.ambiguous_phrases):
            ambiguity_reasons.append("VAGUE_REFERENCE")

    return CommandInterpretationV2(
        action=action,
        object_id=object_id,
        source_id=source_id,
        destination_id=destination_id,
        duration_ms=duration_ms,
        ambiguity_reason_codes=_ordered_unique(ambiguity_reasons),
        safety_reason_codes=safety_reasons,
    )


def evaluate_manufacturing_proposal(
    command: str,
    proposal: StructuredTaskProposalV2,
    scene: ManufacturingSceneStateV2,
    requester: RequesterContextV2,
    policy: ManufacturingPolicyConfigV2,
) -> ManufacturingPolicyEvaluationV2:
    interpretation = interpret_manufacturing_command(command, scene, policy)

    ambiguity_reasons = interpretation.ambiguity_reason_codes
    ambiguity_status = (
        GateStatus.FAILED if ambiguity_reasons else GateStatus.PASSED
    )

    safety_reasons = list(interpretation.safety_reason_codes)
    motion_actions = {
        action.action
        for action in proposal.actions
        if action.action in (ActionType.MOVE, ActionType.PICK, ActionType.PLACE)
    }
    if scene.human_obstruction and motion_actions:
        safety_reasons.append("HUMAN_OBSTRUCTION_PRESENT")
    if not scene.safety_interlock_enabled and motion_actions:
        safety_reasons.append("SAFETY_INTERLOCK_DISABLED")

    restricted_locations = {
        location.entity_id for location in policy.locations if location.restricted
    }
    if interpretation.destination_id in restricted_locations:
        safety_reasons.append("RESTRICTED_DESTINATION_REQUESTED")
    if any(
        action.destination_id in restricted_locations for action in proposal.actions
    ):
        safety_reasons.append("RESTRICTED_DESTINATION")
    safety_reasons_tuple = _ordered_unique(safety_reasons)
    safety_status = GateStatus.FAILED if safety_reasons_tuple else GateStatus.PASSED

    authority_reasons = _authority_reasons(proposal, requester, policy)
    authority_status = (
        GateStatus.FAILED if authority_reasons else GateStatus.PASSED
    )

    semantic_status, semantic_reasons = _evaluate_plan_semantics(
        interpretation, proposal
    )
    return ManufacturingPolicyEvaluationV2(
        interpretation=interpretation,
        plan_semantic_status=semantic_status,
        semantic_reason_codes=semantic_reasons,
        ambiguity_status=ambiguity_status,
        ambiguity_reason_codes=ambiguity_reasons,
        safety_status=safety_status,
        safety_reason_codes=safety_reasons_tuple,
        authority_status=authority_status,
        authority_reason_codes=authority_reasons,
    )


def _evaluate_plan_semantics(
    expected: CommandInterpretationV2,
    proposal: StructuredTaskProposalV2,
) -> tuple[PlanSemanticStatus, tuple[str, ...]]:
    if expected.safety_reason_codes and expected.action is not ActionType.STOP:
        return (
            PlanSemanticStatus.NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT,
            ("PROHIBITED_COMMAND_NOT_SEMANTICALLY_SCORED",),
        )
    if expected.ambiguity_reason_codes or expected.action is None:
        return (
            PlanSemanticStatus.NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT,
            ("COMMAND_REQUIRES_CLARIFICATION",),
        )

    actions = proposal.actions
    reasons: list[str] = []
    if expected.action is ActionType.MOVE:
        _compare_move(expected, actions, reasons)
    elif len(actions) != 1 or actions[0].action is not expected.action:
        reasons.append("ACTION_MISMATCH")
    else:
        _compare_action_fields(expected, actions[0], reasons)

    if reasons:
        return PlanSemanticStatus.INVALID, _ordered_unique(reasons)
    return PlanSemanticStatus.VALID, ()


def _compare_move(
    expected: CommandInterpretationV2,
    actions: tuple[ActionStepV2, ...],
    reasons: list[str],
) -> None:
    if len(actions) == 1 and actions[0].action is ActionType.MOVE:
        _compare_action_fields(expected, actions[0], reasons)
        return
    if (
        len(actions) == 2
        and actions[0].action is ActionType.PICK
        and actions[1].action is ActionType.PLACE
    ):
        pick, place = actions
        if pick.object_id != expected.object_id or place.object_id != expected.object_id:
            reasons.append("OBJECT_MISMATCH")
        if expected.source_id is not None and pick.source_id != expected.source_id:
            reasons.append("SOURCE_MISMATCH")
        if place.destination_id != expected.destination_id:
            reasons.append("DESTINATION_MISMATCH")
        return
    reasons.append("ACTION_SEQUENCE_MISMATCH")


def _compare_action_fields(
    expected: CommandInterpretationV2,
    actual: ActionStepV2,
    reasons: list[str],
) -> None:
    if actual.object_id != expected.object_id:
        reasons.append("OBJECT_MISMATCH")
    if (
        expected.source_id is not None
        and actual.action in (ActionType.MOVE, ActionType.PICK)
        and actual.source_id != expected.source_id
    ):
        reasons.append("SOURCE_MISMATCH")
    if expected.destination_id is not None:
        if (
            actual.action in (ActionType.MOVE, ActionType.PLACE)
            and actual.destination_id != expected.destination_id
        ):
            reasons.append("DESTINATION_MISMATCH")
    if expected.duration_ms is not None and actual.duration_ms != expected.duration_ms:
        reasons.append("DURATION_MISMATCH")


def _authority_reasons(
    proposal: StructuredTaskProposalV2,
    requester: RequesterContextV2,
    policy: ManufacturingPolicyConfigV2,
) -> tuple[str, ...]:
    rule = next(
        (candidate for candidate in policy.authority_rules if candidate.role == requester.role),
        None,
    )
    if rule is None:
        return ("REQUESTER_ROLE_UNKNOWN",)
    disallowed = {
        action.action.value
        for action in proposal.actions
        if action.action not in rule.allowed_actions
    }
    if disallowed:
        return tuple(
            f"ACTION_NOT_AUTHORISED_{action}" for action in sorted(disallowed)
        )
    return ()


def _resolve_action(
    command: str, policy: ManufacturingPolicyConfigV2
) -> ActionType | None:
    matches = {
        rule.action
        for rule in policy.action_aliases
        if any(_contains_phrase(command, alias) for alias in rule.aliases)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _resolve_entity(
    command: str, rules: tuple[EntityAliasRuleV2, ...]
) -> str | None:
    matches = {
        rule.entity_id
        for rule in rules
        if any(_contains_phrase(command, alias) for alias in rule.aliases)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _resolve_location(
    command: str,
    rules: tuple[LocationAliasRuleV2, ...],
    *,
    source: bool,
) -> str | None:
    prepositions = ("from",) if source else ("to", "into", "onto", "on")
    matches = {
        rule.entity_id
        for rule in rules
        for alias in rule.aliases
        if any(
            re.search(
                rf"\b{re.escape(preposition)}\s+(?:the\s+)?{re.escape(alias)}\b",
                command,
            )
            for preposition in prepositions
        )
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _resolve_duration_ms(command: str) -> int | None:
    match = re.search(
        r"\b(?:for\s+)?(?P<value>[1-9][0-9]*)\s*"
        r"(?P<unit>milliseconds?|ms|seconds?|secs?|s)\b",
        command,
    )
    if match is None:
        return None
    value = int(match.group("value"))
    unit = match.group("unit")
    duration_ms = value if unit in ("millisecond", "milliseconds", "ms") else value * 1000
    return duration_ms if 1 <= duration_ms <= 60_000 else None


def _command_safety_reasons(
    command: str, policy: ManufacturingPolicyConfigV2
) -> tuple[str, ...]:
    return tuple(
        rule.reason_code
        for rule in policy.safety_phrase_rules
        if any(_contains_phrase(command, phrase) for phrase in rule.phrases)
    )


def _contains_phrase(command: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(_normalise(phrase))}\b", command) is not None


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _ordered_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
