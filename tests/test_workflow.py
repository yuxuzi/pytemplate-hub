"""The workflow that runs untrusted template code must stay isolated."""

import re
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

    assert steps.index("check-claims") < steps.index("verify --index ../head/index")


def test_workflow_handles_a_base_with_no_index_yet() -> None:
    assert "mkdir -p index" in _steps()


def _step_blocks(steps: str) -> list[str]:
    """Split the steps text into one block per step, starting at each `- ` line."""
    blocks: list[str] = []
    for line in steps.splitlines():
        if line.startswith("      - ") or line.startswith("    steps:"):
            blocks.append("")
        if blocks:
            blocks[-1] += line + "\n"
    return blocks


def test_base_checkout_uses_the_base_sha_at_path_base() -> None:
    steps = _steps()

    assert "ref: ${{ github.event.pull_request.base.sha }}" in steps
    base = [b for b in _step_blocks(steps) if "ref: ${{ github.event.pull_request.base.sha }}" in b]
    assert len(base) == 1
    assert "path: base" in base[0]


def test_head_checkout_is_the_pull_request_at_path_head() -> None:
    steps = _steps()
    head = [b for b in _step_blocks(steps) if "path: head" in b]

    assert len(head) == 1
    assert "ref:" not in head[0]


def test_both_checkouts_keep_no_credentials() -> None:
    checkouts = [b for b in _step_blocks(_steps()) if "actions/checkout" in b]

    assert len(checkouts) == 2
    assert all("persist-credentials: false" in b for b in checkouts)


def test_tooling_runs_only_in_the_base_checkout() -> None:
    steps = _steps()

    assert steps.count("uv sync --locked") == 1
    sync = [b for b in _step_blocks(steps) if "uv sync --locked" in b]
    assert "working-directory: base" in sync[0]
    invocations = [line for line in steps.splitlines() if "uv run pytemplate_hub" in line]
    assert len(invocations) == 2
    for block in _step_blocks(steps):
        if "uv run pytemplate_hub" in block or "uv sync --locked" in block:
            assert "working-directory: base" in block


def test_check_claims_reads_the_head_index_as_data() -> None:
    assert "uv run pytemplate_hub check-claims --base index --index ../head/index" in _steps()


def test_verify_reads_the_head_index_as_data() -> None:
    assert "uv run pytemplate_hub verify --index ../head/index --run-lifecycle" in _steps()


PAGES = Path(__file__).parent.parent / ".github" / "workflows" / "pages.yml"


def test_pages_workflow_runs_no_pack_code() -> None:
    text = "\n".join(
        line
        for line in PAGES.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "run-lifecycle" not in text
    assert "verify" not in text
    assert "pytemplate_hub site" in text


def test_pages_workflow_grants_only_what_publishing_needs() -> None:
    text = "\n".join(
        line
        for line in PAGES.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "permissions:\n  contents: read\n" in text
    assert "pages: write" in text
    assert "id-token: write" in text
    assert "secrets." not in text
    assert "pull_request" not in text


SCHEDULED = Path(__file__).parent.parent / ".github" / "workflows" / "verify-scheduled.yml"


def _scheduled_jobs() -> tuple[str, str]:
    """Return the text of the `verify` and `report` jobs, with comments removed."""
    text = "\n".join(
        line
        for line in SCHEDULED.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    verify_text, report_text = text.split("\n  report:\n", 1)
    return verify_text, report_text


def test_scheduled_workflow_has_no_pull_request_trigger() -> None:
    text = "\n".join(
        line
        for line in SCHEDULED.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "pull_request" not in text
    assert "schedule:" in text
    assert 'cron: "17 6 * * 1"' in text
    assert "workflow_dispatch" in text
    assert "permissions:\n  contents: read\n" in text


def test_scheduled_verify_job_has_no_write_access_or_secrets() -> None:
    verify_text, _ = _scheduled_jobs()

    assert "verify:" in verify_text
    assert ": write" not in verify_text
    assert "secrets." not in verify_text
    assert "github.token" not in verify_text
    assert "pytemplate_hub verify --run-lifecycle" in verify_text


def test_scheduled_report_job_runs_no_checkout_uv_or_hub_code() -> None:
    _, report_text = _scheduled_jobs()

    assert "needs: verify" in report_text
    assert "if: failure()" in report_text
    assert "actions/checkout" not in report_text
    assert re.search(r"\buv\b", report_text) is None
    assert "pytemplate_hub" not in report_text


def test_only_the_scheduled_report_job_can_write_issues() -> None:
    verify_text, report_text = _scheduled_jobs()

    assert "issues: write" in report_text
    assert "issues: write" not in verify_text
    assert "GH_TOKEN: ${{ github.token }}" in report_text
    assert "--repo" in report_text


CODEOWNERS = Path(__file__).parent.parent / ".github" / "CODEOWNERS"


def test_codeowners_requires_review_for_entries_code_and_workflows() -> None:
    lines = [
        line.strip()
        for line in CODEOWNERS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    for path in ("/index/", "/pytemplate_hub/", "/.github/"):
        assert any(line.split()[0] == path and "@yuxuzi" in line for line in lines), path
