from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = REPO_ROOT / "external_references" / "fl-nemotron"


def test_fl_nemotron_reference_snapshot_exists() -> None:
    assert REFERENCE_ROOT.exists()
    assert (REFERENCE_ROOT / "README.md").exists()
    assert (REFERENCE_ROOT / "LICENSE").exists()
    assert (REFERENCE_ROOT / "requirements.txt").exists()
    assert (REFERENCE_ROOT / "src" / "foundry_client.py").exists()
    assert (REFERENCE_ROOT / "src" / "_nemotron_live.py").exists()


def test_runtime_guardrail_document_exists() -> None:
    guardrail = REFERENCE_ROOT / "DO_NOT_MODIFY_PROTOTYPE5_RUNTIME.md"
    text = guardrail.read_text(encoding="utf-8")
    assert "not imported by Prototype 5" in text
    assert "not part of the tested Prototype 5 runtime" in text


def test_external_reference_documentation_exists() -> None:
    doc = REPO_ROOT / "docs" / "prototype5" / "phase2_external_reference_fl_nemotron.md"
    text = doc.read_text(encoding="utf-8")
    assert "M15A.2 remains valid" in text
    assert "M15B.0 remains valid" in text
    assert "future voice-derived command extension" in text
    assert "deterministic validation decides" in text


def test_prototype5_runtime_does_not_import_external_reference() -> None:
    runtime_roots = [REPO_ROOT / "src", REPO_ROOT / "scripts"]
    forbidden_patterns = (
        "import external_references",
        "from external_references",
        "external_references.fl",
        "external_references/fl",
        "external_references\\fl",
    )
    offenders: list[str] = []
    for root in runtime_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern in text for pattern in forbidden_patterns):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_protected_dependency_and_config_files_not_staged() -> None:
    protected_names = {
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "package-lock.json",
        "Dockerfile",
        ".github/workflows",
        "dissertation_drafts/DISS_DRAFT_cleaned.tex",
    }
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    staged = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    assert not any(
        path in protected_names or path.startswith(".github/workflows/")
        for path in staged
    )
