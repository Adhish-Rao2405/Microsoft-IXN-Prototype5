"""Generate deterministic D4.3 modality-invariance research evidence."""

from __future__ import annotations

import hashlib
import importlib
import json
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_REPOSITORY_SHA = "f8d8894e2c6fd7d1076da02ecef3018b04a5f9fa"
BRANCH = "feature/d4-3-modality-invariance"
DATASET_SHA256 = "03bed446d96184a12e67123c177783aabbfe8df6ae9f6629446f13fab6b8cf51"
QUALIFIED_TEST_SHA256 = "4b6fc92c1ce2fc604a25564151e4eee7875fc8134103075f44d4bd729daf5422"
SCHEMA_VERSION = "1.0.0"
EXPERIMENT_ID = "D4_3_TYPED_VS_OPERATOR_REVIEWED_VOICE_MODALITY_INVARIANCE"
OBSERVED_CLAIM = (
    "No modality-induced divergence was observed across 18 controlled paired "
    "requests when typed command text and operator-reviewed voice command text "
    "were held equal."
)
CLAIM_BOUNDARY_TEXT = (
    "This experiment evaluates downstream governance-path invariance after "
    "operator review. It does not evaluate microphone capture fidelity, ASR "
    "accuracy, real Nemotron transcription quality, model stochasticity, "
    "downstream geometric validity or physical execution safety."
)
CLAIM_BOUNDARY = {
    "evaluates_asr_accuracy": False,
    "evaluates_downstream_geometric_validity": False,
    "evaluates_model_stochasticity": False,
    "evaluates_physical_execution": False,
    "evaluates_real_microphone": False,
    "evaluates_real_nemotron": False,
    "operator_reviewed_text_is_governance_command": True,
    "physical_execution_authority_state": "NOT_IMPLEMENTED",
    "raw_transcript_is_untrusted_provenance": True,
}

DATASET_PATH = Path("configs/prototype5/d4_3_modality_invariance_matrix_v1.json")
QUALIFIED_TEST_PATH = Path("tests/prototype5/test_d4_3_modality_invariance.py")
EVALUATOR_PATH = Path("scripts/prototype5/run_d4_3_modality_invariance.py")
PAIRS_PATH = Path("results/prototype5/mode_voice/d4_3_modality_invariance_pairs.jsonl")
SUMMARY_JSON_PATH = Path("results/prototype5/mode_voice/d4_3_modality_invariance_summary.json")
SUMMARY_MD_PATH = Path("results/prototype5/mode_voice/d4_3_modality_invariance_summary.md")
EVIDENCE_SHA_PATH = Path("results/prototype5/mode_voice/d4_3_modality_invariance_evidence.sha256")
DOCUMENTATION_PATH = Path(
    "docs/prototype5/d4_3_typed_vs_operator_reviewed_voice_modality_invariance.md"
)
CI_WORKFLOW_PATH = Path(".github/workflows/prototype5-tests.yml")
BLOG_ROOT_PATH = Path("docs/microsoft_blog")

PROTECTED_PATHS = {
    Path("D3_3_corrected_source_mutation.patch"),
    Path("D3_3_source_mutation.patch"),
}
ALLOWED_WORKTREE_PATHS = {
    DATASET_PATH,
    QUALIFIED_TEST_PATH,
    EVALUATOR_PATH,
    PAIRS_PATH,
    SUMMARY_JSON_PATH,
    SUMMARY_MD_PATH,
    EVIDENCE_SHA_PATH,
    DOCUMENTATION_PATH,
    CI_WORKFLOW_PATH,
    *PROTECTED_PATHS,
}
REQUIRED_WORKTREE_PATHS = {
    DATASET_PATH,
    QUALIFIED_TEST_PATH,
    EVALUATOR_PATH,
    *PROTECTED_PATHS,
}

SOURCE_INPUT_PATHS = tuple(
    sorted(
        (
            DATASET_PATH,
            QUALIFIED_TEST_PATH,
            EVALUATOR_PATH,
            Path("configs/prototype5/final_demo_scenarios_v1.json"),
            Path("configs/prototype5/hybrid_routing_policy_v1.json"),
            Path("configs/prototype5/manufacturing_policy_v2.json"),
            Path("tests/prototype5/d2_3_e2e_server.py"),
            Path("src/prototype5/canonical_governance_runner.py"),
            Path("src/prototype5/demo_service.py"),
            Path("src/prototype5/execution_session.py"),
            Path("src/prototype5/final_demo_contract.py"),
            Path("src/prototype5/final_demo_presentation.py"),
            Path("src/prototype5/foundry_sdk_backend.py"),
            Path("src/prototype5/governance_contract_v2.py"),
            Path("src/prototype5/hybrid_inference_router.py"),
            Path("src/prototype5/manufacturing_policy_v2.py"),
            Path("src/prototype5/recorded_speech.py"),
            Path("src/prototype5/task_proposal_v2.py"),
        ),
        key=lambda path: path.as_posix(),
    )
)


class EvidenceGenerationError(RuntimeError):
    """Fail-closed D4.3 evaluator error."""


@dataclass(frozen=True)
class TestQualification:
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    xfailed: int
    outcomes: dict[str, str]


class _PytestOutcomeCapture:
    def __init__(self) -> None:
        self.outcomes: dict[str, str] = {}
        self.setup_errors: set[str] = set()

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call":
            outcome = "XFAILED" if hasattr(report, "wasxfail") else report.outcome.upper()
            self.outcomes[report.nodeid] = outcome
        elif report.when in {"setup", "teardown"} and report.failed:
            self.setup_errors.add(report.nodeid)


def _repository_path(relative_path: Path) -> Path:
    return ROOT / relative_path


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(relative_path: Path) -> str:
    path = _repository_path(relative_path)
    if not path.is_file():
        raise EvidenceGenerationError(f"required file is missing: {relative_path.as_posix()}")
    return _sha256_bytes(path.read_bytes())


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.replace("\r\n", "\n").strip()


def _git_status_porcelain() -> str:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=10,
    )
    if completed.returncode != 0:
        raise EvidenceGenerationError(
            "git status --porcelain=v1 failed with exit code "
            f"{completed.returncode}: {completed.stderr.strip()}"
        )
    return completed.stdout.replace("\r\n", "\n")


def _parse_status_paths(raw_status: str) -> set[Path]:
    paths: set[Path] = set()
    for line_number, record in enumerate(raw_status.splitlines(), start=1):
        if not record:
            continue
        if len(record) < 4:
            raise EvidenceGenerationError(
                f"malformed git porcelain record at line {line_number}: {record!r}"
            )
        if record[2] != " ":
            raise EvidenceGenerationError(
                "unexpected git porcelain record separator at line "
                f"{line_number}: {record!r}"
            )

        index_status = record[0]
        worktree_status = record[1]
        if index_status in {"R", "C"} or worktree_status in {"R", "C"}:
            raise EvidenceGenerationError(
                "rename/copy git status record is outside the D4.3 parser contract: "
                f"{record!r}"
            )

        raw_path = record[3:]
        if not raw_path:
            raise EvidenceGenerationError(
                f"empty path in git porcelain record at line {line_number}: {record!r}"
            )
        paths.add(Path(raw_path.replace("\\", "/")))
    return paths


def _status_paths() -> set[Path]:
    return _parse_status_paths(_git_status_porcelain())


def _blog_snapshot() -> dict[Path, str]:
    repository_root = ROOT.resolve(strict=True)
    blog_root = _repository_path(BLOG_ROOT_PATH).resolve(strict=True)
    try:
        blog_root.relative_to(repository_root)
    except ValueError as error:
        raise EvidenceGenerationError("blog root escapes repository root") from error

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    snapshot: dict[Path, str] = {}
    pending = [blog_root]
    while pending:
        directory = pending.pop()
        metadata = directory.lstat()
        if directory.is_symlink() or (
            getattr(metadata, "st_file_attributes", 0) & reparse_flag
        ):
            raise EvidenceGenerationError(
                f"blog contains a reparse directory: {directory.relative_to(repository_root).as_posix()}"
            )
        for child in sorted(directory.iterdir(), key=lambda path: path.name):
            child_metadata = child.lstat()
            relative_path = child.relative_to(repository_root)
            resolved_child = child.resolve(strict=True)
            try:
                resolved_child.relative_to(blog_root)
            except ValueError as error:
                raise EvidenceGenerationError(
                    f"blog path escapes approved subtree: {relative_path.as_posix()}"
                ) from error
            if child.is_symlink() or (
                getattr(child_metadata, "st_file_attributes", 0) & reparse_flag
            ):
                raise EvidenceGenerationError(
                    f"blog contains a reparse point: {relative_path.as_posix()}"
                )
            if stat.S_ISDIR(child_metadata.st_mode):
                pending.append(child)
            elif stat.S_ISREG(child_metadata.st_mode):
                snapshot[relative_path] = _sha256_bytes(child.read_bytes())
            else:
                raise EvidenceGenerationError(
                    f"blog contains a non-regular item: {relative_path.as_posix()}"
                )
    return dict(sorted(snapshot.items(), key=lambda item: item[0].as_posix()))


def _assert_blog_snapshot(expected: dict[Path, str]) -> None:
    actual = _blog_snapshot()
    if actual != expected:
        changed = sorted(
            path.as_posix()
            for path in set(expected) | set(actual)
            if expected.get(path) != actual.get(path)
        )
        raise EvidenceGenerationError(
            f"unrelated blog subtree changed during evaluation: {changed}"
        )


def _verify_locked_inputs() -> tuple[dict[str, Any], dict[Path, str]]:
    git_root = Path(_git("rev-parse", "--show-toplevel")).resolve(strict=True)
    expected_root = ROOT.resolve(strict=True)
    if git_root != expected_root:
        raise EvidenceGenerationError("repository root does not match evaluator root")
    if _git("rev-parse", "HEAD").lower() != BASE_REPOSITORY_SHA:
        raise EvidenceGenerationError("base repository SHA mismatch")
    if _git("branch", "--show-current") != BRANCH:
        raise EvidenceGenerationError("D4.3 branch mismatch")
    if _git("merge-base", "HEAD", BASE_REPOSITORY_SHA).lower() != BASE_REPOSITORY_SHA:
        raise EvidenceGenerationError("D4.3 merge-base mismatch")
    if _git("diff", "--cached", "--name-only"):
        raise EvidenceGenerationError("staged changes are forbidden")
    tracked_changes = {
        Path(path.replace("\\", "/"))
        for path in _git("diff", "--name-only").splitlines()
        if path
    }
    unexpected_tracked = tracked_changes - {CI_WORKFLOW_PATH}
    if unexpected_tracked:
        raise EvidenceGenerationError(
            "unexpected tracked working-tree changes: "
            f"{sorted(path.as_posix() for path in unexpected_tracked)}"
        )

    blog_snapshot = _blog_snapshot()
    status_paths = _status_paths()
    unexpected = status_paths - ALLOWED_WORKTREE_PATHS - set(blog_snapshot)
    missing = REQUIRED_WORKTREE_PATHS - status_paths
    if unexpected:
        raise EvidenceGenerationError(
            f"unexpected working-set paths: {sorted(path.as_posix() for path in unexpected)}"
        )
    if missing:
        raise EvidenceGenerationError(
            f"required untracked paths absent: {sorted(path.as_posix() for path in missing)}"
        )

    dataset_sha = _sha256_file(DATASET_PATH)
    test_sha = _sha256_file(QUALIFIED_TEST_PATH)
    if dataset_sha != DATASET_SHA256:
        raise EvidenceGenerationError("qualified dataset SHA-256 mismatch")
    if test_sha != QUALIFIED_TEST_SHA256:
        raise EvidenceGenerationError("qualified test SHA-256 mismatch")

    dataset = json.loads(_repository_path(DATASET_PATH).read_text(encoding="utf-8"))
    if dataset.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceGenerationError("dataset schema version mismatch")
    if dataset.get("experiment_id") != EXPERIMENT_ID:
        raise EvidenceGenerationError("dataset experiment ID mismatch")
    condition_count = len(dataset.get("conditions", ()))
    mode_count = len(dataset.get("routing_modes", ()))
    if condition_count != 6 or mode_count != 3 or condition_count * mode_count != 18:
        raise EvidenceGenerationError("dataset does not define the qualified 6 x 3 matrix")
    return dataset, blog_snapshot


def _run_prerequisite_tests() -> TestQualification:
    capture = _PytestOutcomeCapture()
    exit_code = pytest.main(
        [QUALIFIED_TEST_PATH.as_posix(), "-q", "-p", "no:cacheprovider"],
        plugins=[capture],
    )
    outcomes = dict(sorted(capture.outcomes.items()))
    total = len(outcomes)
    passed = sum(outcome == "PASSED" for outcome in outcomes.values())
    failed = sum(outcome == "FAILED" for outcome in outcomes.values())
    skipped = sum(outcome == "SKIPPED" for outcome in outcomes.values())
    xfailed = sum(outcome == "XFAILED" for outcome in outcomes.values())
    errors = len(capture.setup_errors)
    qualification = TestQualification(
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        xfailed=xfailed,
        outcomes=outcomes,
    )
    if exit_code != pytest.ExitCode.OK or qualification != TestQualification(
        total=36,
        passed=36,
        failed=0,
        errors=0,
        skipped=0,
        xfailed=0,
        outcomes=outcomes,
    ):
        raise EvidenceGenerationError(f"D4.3 prerequisite tests failed: {qualification}")
    return qualification


def _load_qualified_harness() -> Any:
    module = importlib.import_module("tests.prototype5.test_d4_3_modality_invariance")
    loaded_path = Path(module.__file__).resolve()
    if loaded_path != _repository_path(QUALIFIED_TEST_PATH).resolve():
        raise EvidenceGenerationError("qualified harness resolved from an unexpected path")
    if _sha256_file(QUALIFIED_TEST_PATH) != QUALIFIED_TEST_SHA256:
        raise EvidenceGenerationError("qualified harness changed while loading")
    return module


def _source_input_manifest() -> tuple[list[dict[str, str]], str]:
    entries = [
        {"relative_path": path.as_posix(), "sha256": _sha256_file(path)}
        for path in SOURCE_INPUT_PATHS
    ]
    canonical = "".join(
        f"{entry['sha256']}  {entry['relative_path']}\n" for entry in entries
    ).encode("utf-8")
    return entries, _sha256_bytes(canonical)


def _negative_control_outcomes(qualification: TestQualification) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for index in range(1, 11):
        control_id = f"N{index:02d}"
        marker = f"::test_n{index:02d}_"
        matches = [
            (node_id, outcome)
            for node_id, outcome in qualification.outcomes.items()
            if marker in node_id
        ]
        if len(matches) != 1:
            raise EvidenceGenerationError(
                f"expected one runtime outcome for {control_id}, observed {len(matches)}"
            )
        node_id, outcome = matches[0]
        controls[control_id] = {"node_id": node_id, "outcome": outcome}
    return controls


def _normalise_command(value: str) -> str:
    return " ".join(value.split())


def _evaluate_pair(harness: Any, case: dict[str, str]) -> dict[str, Any]:
    scenario = harness.SCENARIOS[case["scenario_id"]]
    raw_scenario = harness.SCENARIOS[case["raw_transcript_scenario_id"]]
    typed_command = scenario["command"]
    reviewed_command = scenario["command"]
    raw_transcript = raw_scenario["command"]
    if typed_command != reviewed_command:
        raise EvidenceGenerationError(f"reviewed/typed precondition failed: {case['pair_id']}")
    material_review = case["review_stratum"] == "MATERIAL_OPERATOR_REVIEW"
    if material_review and raw_transcript == reviewed_command:
        raise EvidenceGenerationError(f"material-review precondition failed: {case['pair_id']}")
    if not material_review and raw_transcript != reviewed_command:
        raise EvidenceGenerationError(f"identity-review precondition failed: {case['pair_id']}")

    typed = harness._build_harness(
        raw_transcript=raw_transcript,
        transcription_id=f"d4-3-evidence-unused-typed-{case['pair_id'].lower()}",
    )
    voice = harness._build_harness(
        raw_transcript=raw_transcript,
        transcription_id=f"d4-3-evidence-voice-{case['pair_id'].lower()}",
    )
    if typed.initial_operational_projection != voice.initial_operational_projection:
        raise EvidenceGenerationError(f"initial router state differs: {case['pair_id']}")

    typed_result = harness._typed_result(
        typed,
        scenario_id=case["scenario_id"],
        command=typed_command,
        mode=case["routing_mode"],
    )
    voice_result = harness._voice_result(
        voice,
        scenario_id=case["scenario_id"],
        reviewed_command=reviewed_command,
        mode=case["routing_mode"],
    )
    p1_typed = harness.P1_CANONICAL_GOVERNANCE_INPUT_PROJECTION(typed_result)
    p1_voice = harness.P1_CANONICAL_GOVERNANCE_INPUT_PROJECTION(voice_result)
    p2_typed = harness.P2_PROVIDER_PROPOSAL_CONTROL_PROJECTION(typed_result)
    p2_voice = harness.P2_PROVIDER_PROPOSAL_CONTROL_PROJECTION(voice_result)
    p3_typed = harness.P3_GOVERNANCE_OUTCOME_PROJECTION(typed_result)
    p3_voice = harness.P3_GOVERNANCE_OUTCOME_PROJECTION(voice_result)
    p4_typed = harness.P4_AUTHORITY_PROJECTION(
        typed_result, typed.service, scenario_id=case["scenario_id"]
    )
    p4_voice = harness.P4_AUTHORITY_PROJECTION(
        voice_result, voice.service, scenario_id=case["scenario_id"]
    )
    p5_typed = harness.P5_ROUTER_OPERATIONAL_CONTROL_PROJECTION(
        typed_result["local_health"]
    )
    p5_voice = harness.P5_ROUTER_OPERATIONAL_CONTROL_PROJECTION(
        voice_result["local_health"]
    )

    typed_record = typed_result["canonical_result"]["governance_record"]
    voice_record = voice_result["canonical_result"]["governance_record"]
    observed_differences = harness._differing_leaf_paths(typed_result, voice_result)
    allowed_differences = (
        harness.RESULT_MODALITY_PROVENANCE_LEAF_PATHS
        | harness.RESULT_VOLATILE_LEAF_PATHS
    )
    unexpected_difference_paths = sorted(observed_differences - allowed_differences)
    p1_match = p1_typed == p1_voice
    p2_match = p2_typed == p2_voice
    p3_match = p3_typed == p3_voice
    p4_match = p4_typed == p4_voice
    decision_match = typed_record["final_decision"] == voice_record["final_decision"]
    gate_vector_match = (
        typed_record["parse_status"],
        typed_record["json_status"],
        typed_record["schema_status"],
        typed_record["plan_semantic_status"],
        typed_record["ambiguity_status"],
        typed_record["safety_status"],
        typed_record["authority_status"],
        typed_record["gate_reasons"],
    ) == (
        voice_record["parse_status"],
        voice_record["json_status"],
        voice_record["schema_status"],
        voice_record["plan_semantic_status"],
        voice_record["ambiguity_status"],
        voice_record["safety_status"],
        voice_record["authority_status"],
        voice_record["gate_reasons"],
    )
    eligibility_match = (
        typed_record["execution_eligible"] == voice_record["execution_eligible"]
    )
    raw_authority_violation = not (
        voice_record["original_transcript_text"] == raw_transcript
        and voice_record["normalised_command"] == _normalise_command(reviewed_command)
    )
    expected_decision_match = (
        typed_record["final_decision"]
        == voice_record["final_decision"]
        == case["expected_decision"]
    )
    replay_scenario_match = (
        p4_typed["replay_policy_scenario_id"]
        == p4_voice["replay_policy_scenario_id"]
        == case["scenario_id"]
    )
    physical_authority_valid = (
        p4_typed["physical_execution_authority"]
        == p4_voice["physical_execution_authority"]
        == "NOT_IMPLEMENTED"
    )
    network_counts = {
        "typed_cloud": typed.cloud_backend.network_call_count,
        "typed_local": typed.local_backend.network_call_count,
        "voice_cloud": voice.cloud_backend.network_call_count,
        "voice_local": voice.local_backend.network_call_count,
    }
    invariant = all(
        (
            typed_command == reviewed_command,
            p1_match,
            p2_match,
            p3_match,
            p4_match,
            decision_match,
            gate_vector_match,
            eligibility_match,
            not unexpected_difference_paths,
            not raw_authority_violation,
            expected_decision_match,
            physical_authority_valid,
            replay_scenario_match,
            all(count == 0 for count in network_counts.values()),
        )
    )

    return {
        "authority_projection_match": p4_match,
        "canonical_input_match": p1_match,
        "claim_boundary": CLAIM_BOUNDARY,
        "condition_id": case["condition_id"],
        "decision_match": decision_match,
        "execution_eligibility_match": eligibility_match,
        "expected_final_decision": case["expected_decision"],
        "experiment_id": EXPERIMENT_ID,
        "gate_vector_match": gate_vector_match,
        "input_provenance": {
            "canonical_command_source": "configs/prototype5/final_demo_scenarios_v1.json",
            "dataset": DATASET_PATH.as_posix(),
            "qualified_harness": QUALIFIED_TEST_PATH.as_posix(),
            "raw_transcript_source_scenario_id": case["raw_transcript_scenario_id"],
        },
        "invariant": invariant,
        "p1_typed": p1_typed,
        "p1_voice": p1_voice,
        "p2_typed": p2_typed,
        "p2_voice": p2_voice,
        "p3_typed": p3_typed,
        "p3_voice": p3_voice,
        "p4_typed": p4_typed,
        "p4_voice": p4_voice,
        "p5_typed_diagnostic": p5_typed,
        "p5_voice_diagnostic": p5_voice,
        "pair_id": case["pair_id"],
        "provider_proposal_match": p2_match,
        "raw_transcript_authority_violation": raw_authority_violation,
        "replay_policy_scenario_id_match": replay_scenario_match,
        "requested_inference_mode": case["routing_mode"],
        "review_stratum": case["review_stratum"],
        "routing_control": {
            "initial_router_state_match": True,
            "network_call_counts": network_counts,
        },
        "scenario_id": case["scenario_id"],
        "schema_version": SCHEMA_VERSION,
        "typed_command_text": typed_command,
        "unexpected_difference_paths": unexpected_difference_paths,
        "voice_raw_transcript_text": raw_transcript,
        "voice_reviewed_command_text": reviewed_command,
        "governance_outcome_match": p3_match,
    }


def _count(records: list[dict[str, Any]], predicate: Any) -> int:
    return sum(bool(predicate(record)) for record in records)


def _metrics(
    records: list[dict[str, Any]],
    qualification: TestQualification,
    harness: Any,
) -> dict[str, Any]:
    unknown_canonical = sorted(
        harness._model_leaf_paths(harness.CanonicalGovernanceRequestV2)
        - (
            harness.CANONICAL_SEMANTIC_LEAF_PATHS
            | harness.CANONICAL_MODALITY_PROVENANCE_LEAF_PATHS
        )
    )
    known_result = (
        harness.RESULT_P1_LEAF_PATHS
        | harness.RESULT_P2_LEAF_PATHS
        | harness.RESULT_P3_LEAF_PATHS
        | harness.RESULT_P4_LEAF_PATHS
        | harness.RESULT_P5_OPERATIONAL_LEAF_PATHS
        | harness.RESULT_MODALITY_PROVENANCE_LEAF_PATHS
        | harness.RESULT_VOLATILE_LEAF_PATHS
    )
    unknown_result = sorted(
        harness._model_leaf_paths(harness.HybridGovernanceResultV1) - known_result
    )
    mode = lambda name: lambda row: row["requested_inference_mode"] == name
    outcome = lambda name: lambda row: row["expected_final_decision"] == name
    invariant_for = lambda predicate: lambda row: predicate(row) and row["invariant"]
    network_total = lambda name: sum(
        sum(row["routing_control"]["network_call_counts"].values())
        for row in records
        if row["requested_inference_mode"] == name
    )
    auto_providers = sorted(
        {
            row["p2_typed"]["selected_provider"]
            for row in records
            if row["requested_inference_mode"] == "AUTO"
        }
        | {
            row["p2_voice"]["selected_provider"]
            for row in records
            if row["requested_inference_mode"] == "AUTO"
        }
    )
    auto_fallbacks = sum(
        int(row[projection]["fallback_triggered"])
        for row in records
        if row["requested_inference_mode"] == "AUTO"
        for projection in ("p2_typed", "p2_voice")
    )
    return {
        "accept_pair_count": _count(records, outcome("ACCEPT")),
        "accept_pair_invariant_count": _count(records, invariant_for(outcome("ACCEPT"))),
        "auto_controlled_network_call_count": network_total("AUTO"),
        "auto_fallback_occurrence_count": auto_fallbacks,
        "auto_pair_count": _count(records, mode("AUTO")),
        "auto_pair_invariant_count": _count(records, invariant_for(mode("AUTO"))),
        "auto_selected_providers": auto_providers,
        "clarify_pair_count": _count(records, outcome("CLARIFY")),
        "clarify_pair_invariant_count": _count(records, invariant_for(outcome("CLARIFY"))),
        "cloud_controlled_network_call_count": network_total("CLOUD"),
        "cloud_pair_count": _count(records, mode("CLOUD")),
        "cloud_pair_invariant_count": _count(records, invariant_for(mode("CLOUD"))),
        "decision_match_count": _count(records, lambda row: row["decision_match"]),
        "execution_eligibility_match_count": _count(
            records, lambda row: row["execution_eligibility_match"]
        ),
        "gate_vector_match_count": _count(records, lambda row: row["gate_vector_match"]),
        "identity_review_pair_count": _count(
            records, lambda row: row["review_stratum"] == "IDENTITY_REVIEW"
        ),
        "local_controlled_network_call_count": network_total("LOCAL"),
        "local_pair_count": _count(records, mode("LOCAL")),
        "local_pair_invariant_count": _count(records, invariant_for(mode("LOCAL"))),
        "material_operator_review_pair_count": _count(
            records, lambda row: row["review_stratum"] == "MATERIAL_OPERATOR_REVIEW"
        ),
        "negative_control_count": 10,
        "negative_control_pass_count": sum(
            outcome == "PASSED"
            for node_id, outcome in qualification.outcomes.items()
            if "::test_n" in node_id
        ),
        "p1_match_count": _count(records, lambda row: row["canonical_input_match"]),
        "p2_match_count": _count(records, lambda row: row["provider_proposal_match"]),
        "p3_match_count": _count(records, lambda row: row["governance_outcome_match"]),
        "p4_match_count": _count(records, lambda row: row["authority_projection_match"]),
        "pair_count": len(records),
        "pair_divergence_count": _count(records, lambda row: not row["invariant"]),
        "pair_invariant_count": _count(records, lambda row: row["invariant"]),
        "raw_transcript_authority_violation_count": _count(
            records, lambda row: row["raw_transcript_authority_violation"]
        ),
        "reject_pair_count": _count(records, outcome("REJECT")),
        "reject_pair_invariant_count": _count(records, invariant_for(outcome("REJECT"))),
        "replay_policy_scenario_id_match_count": _count(
            records, lambda row: row["replay_policy_scenario_id_match"]
        ),
        "unexpected_difference_count": sum(
            len(row["unexpected_difference_paths"]) for row in records
        ),
        "unknown_canonical_field_count": len(unknown_canonical),
        "unknown_canonical_fields": unknown_canonical,
        "unknown_result_field_count": len(unknown_result),
        "unknown_result_fields": unknown_result,
    }


def _summary_status(metrics: dict[str, Any], qualification: TestQualification) -> str:
    required_18 = (
        "pair_invariant_count",
        "p1_match_count",
        "p2_match_count",
        "p3_match_count",
        "p4_match_count",
        "decision_match_count",
        "gate_vector_match_count",
        "execution_eligibility_match_count",
        "replay_policy_scenario_id_match_count",
    )
    passed = all(
        (
            metrics["pair_count"] == 18,
            all(metrics[key] == 18 for key in required_18),
            metrics["pair_divergence_count"] == 0,
            metrics["raw_transcript_authority_violation_count"] == 0,
            metrics["unexpected_difference_count"] == 0,
            metrics["negative_control_count"] == 10,
            metrics["negative_control_pass_count"] == 10,
            metrics["unknown_canonical_field_count"] == 0,
            metrics["unknown_result_field_count"] == 0,
            metrics["local_controlled_network_call_count"] == 0,
            metrics["cloud_controlled_network_call_count"] == 0,
            metrics["auto_controlled_network_call_count"] == 0,
            qualification.total == qualification.passed == 36,
            qualification.failed == qualification.errors == qualification.skipped == 0,
            qualification.xfailed == 0,
        )
    )
    return "PASS" if passed else "FAIL"


def _canonical_json_line(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _pretty_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _write_text(relative_path: Path, content: str) -> None:
    path = _repository_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _markdown(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    provenance = summary["provenance"]
    return f"""# D4.3 Typed vs Operator-Reviewed Voice Modality Invariance

## Method

This controlled paired metamorphic experiment holds typed command text and operator-reviewed voice command text equal. Six semantic/review conditions are crossed with LOCAL, CLOUD and AUTO routing modes, yielding 18 pairs. Raw ASR is retained as untrusted provenance. Test-scoped deterministic providers hold proposal generation fixed and require no real network or model service.

## Results

- Overall invariance: {metrics['pair_invariant_count']}/{metrics['pair_count']} pairs.
- Divergence: {metrics['pair_divergence_count']}/{metrics['pair_count']} pairs.
- Negative controls: {metrics['negative_control_pass_count']}/{metrics['negative_control_count']} passed.
- Identity review: {metrics['identity_review_pair_count']}/9 pairs invariant.
- Material operator review: {metrics['material_operator_review_pair_count']}/9 pairs invariant.
- LOCAL: {metrics['local_pair_invariant_count']}/{metrics['local_pair_count']} invariant.
- CLOUD: {metrics['cloud_pair_invariant_count']}/{metrics['cloud_pair_count']} invariant.
- AUTO: {metrics['auto_pair_invariant_count']}/{metrics['auto_pair_count']} invariant.
- ACCEPT: {metrics['accept_pair_invariant_count']}/{metrics['accept_pair_count']} invariant.
- REJECT: {metrics['reject_pair_invariant_count']}/{metrics['reject_pair_count']} invariant.
- CLARIFY: {metrics['clarify_pair_invariant_count']}/{metrics['clarify_pair_count']} invariant.

## Raw vs Reviewed Authority

B1 changes an ambiguous raw transcript to the clear ACCEPT command. B2 changes a clear raw transcript to the unsafe REJECT command. B3 changes a clear raw transcript to the ambiguous CLARIFY command. In every material-review pair, the governance outcome follows the operator-reviewed command; raw-transcript authority violations observed: {metrics['raw_transcript_authority_violation_count']}.

## Governance Projection

P1 compares governance-effective canonical input. P2 proves controlled provider and proposal identity. P3 is the primary governance outcome projection across parse, JSON, schema, semantic, ambiguity, safety, authority, reason and decision fields. P4 compares execution, simulation, exact-scenario replay and physical-authority state. P5 is operational diagnostic evidence only.

## Authority Boundary

Execution eligibility is a governance result. Qualification replay access is a separate exact-scenario presentation policy. Simulation permits, where present, are not physical execution authority. Physical execution authority remains `NOT_IMPLEMENTED`.

## Claim Boundary

{summary['observed_claim']}

{summary['claim_boundary_text']}

## Provenance

- Frozen base repository SHA: `{provenance['base_repository_sha']}`
- Dataset SHA256: `{provenance['dataset_sha256']}`
- Qualified test SHA256: `{provenance['qualified_test_sha256']}`
- Evaluator SHA256: `{provenance['evaluator_sha256']}`
- Source-input manifest SHA256: `{provenance['source_input_manifest_sha256']}`
- Pair JSONL SHA256: `{summary['artifacts']['pairs_jsonl_sha256']}`

The frozen base SHA is not presented as containing the uncommitted D4.3 files. A later Git release SHA will externally seal these evidence bytes.
"""


def _evidence_manifest() -> str:
    paths = sorted(
        (
            DATASET_PATH,
            QUALIFIED_TEST_PATH,
            EVALUATOR_PATH,
            PAIRS_PATH,
            SUMMARY_JSON_PATH,
            SUMMARY_MD_PATH,
        ),
        key=lambda path: path.as_posix(),
    )
    return "".join(f"{_sha256_file(path)}  {path.as_posix()}\n" for path in paths)


def _validate_records(records: list[dict[str, Any]]) -> None:
    if len(records) != 18 or len({record["pair_id"] for record in records}) != 18:
        raise EvidenceGenerationError("pair records are not exactly 18 unique entries")
    for record in records:
        if record["voice_reviewed_command_text"] != record["typed_command_text"]:
            raise EvidenceGenerationError(f"reviewed/typed mismatch: {record['pair_id']}")
        if (
            record["review_stratum"] == "MATERIAL_OPERATOR_REVIEW"
            and record["voice_raw_transcript_text"]
            == record["voice_reviewed_command_text"]
        ):
            raise EvidenceGenerationError(f"material-review raw text not distinct: {record['pair_id']}")
        if record["p4_typed"]["replay_policy_scenario_id"] != record["scenario_id"]:
            raise EvidenceGenerationError(f"typed replay scenario mismatch: {record['pair_id']}")
        if record["p4_voice"]["replay_policy_scenario_id"] != record["scenario_id"]:
            raise EvidenceGenerationError(f"voice replay scenario mismatch: {record['pair_id']}")
        if record["p4_typed"]["physical_execution_authority"] != "NOT_IMPLEMENTED":
            raise EvidenceGenerationError(f"typed physical authority violation: {record['pair_id']}")
        if record["p4_voice"]["physical_execution_authority"] != "NOT_IMPLEMENTED":
            raise EvidenceGenerationError(f"voice physical authority violation: {record['pair_id']}")


def main() -> int:
    _, blog_snapshot = _verify_locked_inputs()
    qualification = _run_prerequisite_tests()
    harness = _load_qualified_harness()
    if len(harness.PAIR_CASES) != 18:
        raise EvidenceGenerationError("qualified harness pair count changed")

    source_entries, source_manifest_sha = _source_input_manifest()
    evaluator_sha = _sha256_file(EVALUATOR_PATH)
    records = [_evaluate_pair(harness, dict(case)) for case in harness.PAIR_CASES]
    _validate_records(records)
    metrics = _metrics(records, qualification, harness)
    status = _summary_status(metrics, qualification)
    if status != "PASS":
        raise EvidenceGenerationError(f"D4.3 summary contract failed: {metrics}")
    _assert_blog_snapshot(blog_snapshot)

    pairs_text = "".join(_canonical_json_line(record) + "\n" for record in records)
    _write_text(PAIRS_PATH, pairs_text)
    pairs_sha = _sha256_file(PAIRS_PATH)
    negative_controls = _negative_control_outcomes(qualification)
    replay_counts: dict[str, int] = {}
    for record in records:
        state = record["p4_typed"]["qualification_replay_access"]
        replay_counts[state] = replay_counts.get(state, 0) + 1

    summary = {
        "artifacts": {
            "pairs_jsonl": PAIRS_PATH.as_posix(),
            "pairs_jsonl_sha256": pairs_sha,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "claim_boundary_text": CLAIM_BOUNDARY_TEXT,
        "dataset_identity": {
            "experiment_id": EXPERIMENT_ID,
            "relative_path": DATASET_PATH.as_posix(),
            "schema_version": SCHEMA_VERSION,
            "sha256": DATASET_SHA256,
        },
        "experiment_id": EXPERIMENT_ID,
        "metrics": metrics,
        "negative_control_outcomes": negative_controls,
        "negative_control_runtime_capture": True,
        "observed_claim": OBSERVED_CLAIM,
        "physical_execution_authority_state": "NOT_IMPLEMENTED",
        "prerequisite_tests": {
            "errors": qualification.errors,
            "failed": qualification.failed,
            "passed": qualification.passed,
            "skipped": qualification.skipped,
            "total": qualification.total,
            "xfailed": qualification.xfailed,
        },
        "provenance": {
            "base_repository_sha": BASE_REPOSITORY_SHA,
            "branch": BRANCH,
            "dataset_sha256": DATASET_SHA256,
            "evaluator_sha256": evaluator_sha,
            "qualified_test_sha256": QUALIFIED_TEST_SHA256,
            "source_input_manifest": source_entries,
            "source_input_manifest_canonicalisation": (
                "UTF-8 lines sorted by POSIX relative path: "
                "<lowercase_sha256><two spaces><relative_path>\\n"
            ),
            "source_input_manifest_sha256": source_manifest_sha,
        },
        "replay_access_counts": dict(sorted(replay_counts.items())),
        "schema_version": SCHEMA_VERSION,
        "status": status,
    }
    _write_text(SUMMARY_JSON_PATH, _pretty_json(summary))
    _write_text(SUMMARY_MD_PATH, _markdown(summary))
    _write_text(EVIDENCE_SHA_PATH, _evidence_manifest())

    written_records = [
        json.loads(line)
        for line in _repository_path(PAIRS_PATH).read_text(encoding="utf-8").splitlines()
    ]
    _validate_records(written_records)
    written_summary = json.loads(
        _repository_path(SUMMARY_JSON_PATH).read_text(encoding="utf-8")
    )
    if written_summary != summary:
        raise EvidenceGenerationError("summary JSON round-trip mismatch")
    _assert_blog_snapshot(blog_snapshot)
    print(
        _pretty_json(
            {
                "evaluator_sha256": evaluator_sha,
                "pair_count": len(records),
                "pair_invariant_count": metrics["pair_invariant_count"],
                "source_input_manifest_sha256": source_manifest_sha,
                "status": status,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
