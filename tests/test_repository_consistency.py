"""Checks that files edited by hand stay consistent with each other."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "google_keep_sync"
TRANSLATIONS = sorted((COMPONENT / "translations").glob("*.json"))
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

# Commit messages the no-attribution-trailers hook and the Commit Trailers CI
# check must reject, and ones they must allow.
REJECTED_MESSAGES = [
    "fix: a\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    "fix: a\n\nCo-authored-by: Codex <noreply@openai.com>",
    "fix: a\n\nCo-authored-by: A Person <person@example.com>",
    "fix: a\n\nco-authored-by:someone",
    "fix: a\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)",
    "fix: a\n\nGenerated with Cursor",
    "fix: a\n\n  - generated with an AI tool",
    "fix: a\n\nClaude-Session: https://claude.ai/code/session_0123",
    "fix: a\n\nAgent-Logs-Url: https://github.com/o/r/sessions/0123",
]
ALLOWED_MESSAGES = [
    "fix: a",
    "fix: a\n\nSigned-off-by: A Person <person@example.com>",
    "fix: handle lists generated with the Keep app",
    "fix: a\n\nThe token is generated with gpsoauth.",
    "docs: explain that a Co-authored-by: line is rejected",
]


def _package(requirement: str) -> str:
    """Return the normalized package name of a requirement."""
    match = re.match(r"[A-Za-z0-9_.\-]+", requirement)
    assert match, f"not a requirement: {requirement!r}"
    return re.sub(r"[-_.]+", "-", match.group(0)).lower()


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Return the strings of a translation file keyed by their dotted path."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


def _load(path: Path) -> dict[str, str]:
    """Load a strings or translation file as flattened strings."""
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


def test_manifest_requirements_match_test_requirements() -> None:
    """Test that the tests install the versions manifest.json gives users."""
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    test_requirements = {
        _package(line): line.strip()
        for line in (ROOT / "requirements.test.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for requirement in manifest["requirements"]:
        name = _package(requirement)
        assert name in test_requirements, (
            f"manifest.json requires {requirement!r}, "
            "which requirements.test.txt doesn't list"
        )
        tested = test_requirements[name]
        assert tested.replace(" ", "") == requirement.replace(" ", ""), (
            f"manifest.json requires {requirement!r} but requirements.test.txt "
            f"has {tested!r}: list the same version in both"
        )


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda path: path.name)
def test_translation_has_the_keys_of_strings_json(path: Path) -> None:
    """Test that a translation has exactly the keys of strings.json."""
    expected = set(_load(COMPONENT / "strings.json"))
    actual = set(_load(path))
    assert not expected - actual, f"{path.name} lacks {sorted(expected - actual)}"
    assert not actual - expected, f"{path.name} has extra {sorted(actual - expected)}"


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda path: path.name)
def test_translation_keeps_the_placeholders_of_english(path: Path) -> None:
    """Test that a translation uses the same placeholders as en.json."""
    english = _load(COMPONENT / "translations" / "en.json")
    for key, text in _load(path).items():
        if key in english:
            assert sorted(PLACEHOLDER.findall(text)) == sorted(
                PLACEHOLDER.findall(english[key])
            ), f"{path.name}: {key} changes the placeholders of en.json"


def _trailer_patterns() -> tuple[str, str]:
    """Return the trailer regex of the pre-commit hook and of the CI check."""
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hook = next(
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "no-attribution-trailers"
    )
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "commit-trailers.yml").read_text()
    )
    step = workflow["jobs"]["trailers"]["steps"][0]
    return hook["entry"], step["env"]["PATTERN"]


def test_trailer_patterns_match() -> None:
    """Test that the pre-commit hook and the CI check use the same regex."""
    hook_pattern, ci_pattern = _trailer_patterns()
    assert hook_pattern == ci_pattern, (
        "the no-attribution-trailers entry in .pre-commit-config.yaml and PATTERN in "
        "commit-trailers.yml differ: make them identical"
    )


@pytest.mark.parametrize(
    ("message", "rejected"),
    [(message, True) for message in REJECTED_MESSAGES]
    + [(message, False) for message in ALLOWED_MESSAGES],
)
def test_trailer_pattern(message: str, rejected: bool) -> None:
    """Test the pre-commit hook's regex (Python) on a commit message."""
    hook_pattern, _ = _trailer_patterns()
    assert bool(re.search(hook_pattern, message)) is rejected


JQ = shutil.which("jq")


@pytest.mark.skipif(JQ is None, reason="jq isn't installed")
def test_trailer_pattern_in_jq() -> None:
    """Test the CI check's regex in jq, whose regex engine differs from Python's."""
    _, ci_pattern = _trailer_patterns()
    messages = REJECTED_MESSAGES + ALLOWED_MESSAGES
    result = subprocess.run(
        [str(JQ), "-c", "--arg", "re", ci_pattern, "[.[] | test($re)]"],
        input=json.dumps(messages),
        capture_output=True,
        text=True,
        check=True,
    )
    expected = [True] * len(REJECTED_MESSAGES) + [False] * len(ALLOWED_MESSAGES)
    assert json.loads(result.stdout) == expected
