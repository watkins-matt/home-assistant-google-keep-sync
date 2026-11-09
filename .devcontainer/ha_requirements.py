"""Work out what to install next to Home Assistant core in the dev container.

  ha_requirements.py latest
      Print the newest Home Assistant release that
      pytest-homeassistant-custom-component has a release for. Core follows
      this, not the newest Home Assistant release: the plugin must match core
      exactly, and it trails a new release by a few days.

  ha_requirements.py integrations <core checkout> <config dir>
      Print the requirements of the integrations Home Assistant will load: the
      ones named in configuration.yaml, the ones it always loads, the entity
      integrations, their dependencies, and every custom integration. Home Assistant would install
      them at startup; installing them up front gives a clean first start.

  ha_requirements.py tests <requirements.test.txt> <HA version>
      Print JSON {"requirements": [...], "no_deps": [...]} for the test tools,
      matched to the Home Assistant version in the venv:
      pytest-homeassistant-custom-component is replaced by the release built
      for that version, so installing it never replaces the core checkout. If
      there is no such release yet (a new Home Assistant release is usually a
      day or two ahead of it), the newest older one is installed without its
      dependencies, and those are listed by name only.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

PHCC = "pytest-homeassistant-custom-component"
ALWAYS_LOADED = [
    "analytics", "api", "auth", "backup", "config", "frontend", "homeassistant",
    "http", "logger", "network", "onboarding", "person", "recorder", "repairs",
    "search", "system_log", "websocket_api",
]


def integrations(core: Path, config: Path) -> None:
    components = core / "homeassistant" / "components"
    custom = config / "custom_components"
    todo = list(ALWAYS_LOADED)
    configuration = config / "configuration.yaml"
    if configuration.exists():
        todo += re.findall(r"^([a-z0-9_]+):", configuration.read_text(), re.MULTILINE)
    if custom.is_dir():
        todo += [p.name for p in custom.iterdir() if (p / "manifest.json").exists()]
    # Entity integrations (light, infrared, radio_frequency, ...) are set up
    # without being named anywhere.
    for manifest in components.glob("*/manifest.json"):
        if json.loads(manifest.read_text()).get("integration_type") == "entity":
            todo.append(manifest.parent.name)
    requirements: set[str] = set()
    seen: set[str] = set()
    while todo:
        domain = todo.pop()
        if domain in seen:
            continue
        seen.add(domain)
        for base in (custom, components):
            manifest = base / domain / "manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text())
                requirements.update(data.get("requirements", []))
                todo.extend(data.get("dependencies", []))
                break
    print("\n".join(sorted(requirements)))


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def _vtuple(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def _name_as_written(spec: str) -> str:
    return re.match(r"[A-Za-z0-9_.\-]+", spec).group(0)


def _name(spec: str) -> str:
    return re.sub(r"[-_.]+", "-", _name_as_written(spec)).lower()


def tests(requirements_file: Path, ha_version: str) -> None:
    lines = [
        line.strip() for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    others = [line for line in lines if not re.match(rf"{PHCC}\b", line)]
    releases = sorted(
        (v for v in _get(f"https://pypi.org/pypi/{PHCC}/json")["releases"]
         if re.fullmatch(r"\d+\.\d+\.\d+", v)),
        key=_vtuple, reverse=True,
    )
    for version in releases[:80]:
        info = _get(f"https://pypi.org/pypi/{PHCC}/{version}/json")["info"]
        deps = [d for d in info.get("requires_dist") or [] if "extra ==" not in d]
        pin = next((m.group(1) for d in deps if (m := re.match(r"homeassistant\s*==\s*([\w.]+)", d))), None)
        if pin is None or _vtuple(pin) > _vtuple(ha_version):
            continue
        exact = pin == ha_version
        # One entry per package: the plugin's own replace the repository's pins
        # (those were chosen for an older plugin). Without an exact match the
        # plugin's pins are for an older Home Assistant, so only the names are
        # kept and whatever core already installed stays.
        wanted = {_name(line): line for line in others}
        for dep in deps:
            spec = dep.split(";")[0].strip()
            if _name(spec) != "homeassistant":
                wanted[_name(spec)] = spec if exact else _name_as_written(spec)
        result = {
            "requirements": [*wanted.values(), *([f"{PHCC}=={version}"] if exact else [])],
            "no_deps": [] if exact else [f"{PHCC}=={version}"],
        }
        print(json.dumps(result))
        return
    sys.exit(f"no {PHCC} release for Home Assistant {ha_version} or older")


def latest() -> None:
    """Print the newest Home Assistant release the test plugin supports."""
    releases = sorted(
        (v for v in _get(f"https://pypi.org/pypi/{PHCC}/json")["releases"]
         if re.fullmatch(r"\d+\.\d+\.\d+", v)),
        key=_vtuple, reverse=True,
    )
    for version in releases[:20]:
        info = _get(f"https://pypi.org/pypi/{PHCC}/{version}/json")["info"]
        for dep in info.get("requires_dist") or []:
            m = re.match(r"homeassistant\s*==\s*(\d+\.\d+\.\d+)\s*$", dep.split(";")[0])
            if m:
                print(m.group(1))
                return
    sys.exit(f"no {PHCC} release pins a Home Assistant release")


if __name__ == "__main__":
    if sys.argv[1:2] == ["latest"]:
        latest()
    elif sys.argv[1:2] == ["integrations"]:
        integrations(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1:2] == ["tests"]:
        tests(Path(sys.argv[2]), sys.argv[3])
    else:
        sys.exit(__doc__)
