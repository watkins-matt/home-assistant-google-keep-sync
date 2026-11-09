"""Checks that files edited by hand stay consistent with each other."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "google_keep_sync"
TRANSLATIONS = sorted((COMPONENT / "translations").glob("*.json"))
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


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
