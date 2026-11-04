"""The workflow that runs untrusted template code must stay isolated."""

from pathlib import Path

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "verify-index.yml"


def _steps() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("#"))


def test_workflow_has_no_secrets_or_privileged_trigger() -> None:
    steps = _steps()

    assert "secrets." not in steps
    assert "github.token" not in steps
    assert "pull_request_target" not in steps
    assert "workflow_run" not in steps


def test_workflow_token_can_only_read_and_is_not_kept() -> None:
    steps = _steps()

    assert "permissions:\n  contents: read\n" in steps
    assert steps.count(": write") == 0
    assert "persist-credentials: false" in steps


def test_workflow_refuses_review_claims_before_running_pack_code() -> None:
    steps = _steps()

    assert steps.index("check-claims") < steps.index("verify --run-lifecycle")


def test_workflow_handles_a_base_with_no_index_yet() -> None:
    assert 'git cat-file -e "$BASE_SHA:index"' in _steps()
