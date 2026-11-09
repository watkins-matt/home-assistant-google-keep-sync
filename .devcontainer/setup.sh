#!/usr/bin/env bash
# Dev container setup for Google Keep Sync (see "Development" in README.md).
#
#   .devcontainer/setup.sh            first-time setup (onCreateCommand)
#   .devcontainer/setup.sh --update   on every start (postStartCommand)
#
# Lays out /workspaces like this:
#   home-assistant-google-keep-sync/  this repository
#   home-assistant-core/              Home Assistant core (home-assistant/core)
#     config/                         HA config; custom_components/google_keep_sync -> this repo
#   gpsoauth/                         gpsoauth (simon-weber/gpsoauth), for reading and debugging
# and one virtual environment, ~/.venvs/ha, for running Home Assistant and the
# tests: core in editable mode, the packages of the integrations it loads, and
# requirements.test.txt with pytest-homeassistant-custom-component matched to
# core's version (so it can't replace core). ~/.venvs/test links to it.
#
# HA_CORE_REF=latest (default) keeps core on the newest release the test plugin
# (pytest-homeassistant-custom-component) supports, a few days behind a new
# Home Assistant release, so tests and Home Assistant share one version and one
# venv. --update moves it, but only while core is on a release tag with no
# local changes. Check out a branch and it is left alone. Any other value (a
# tag or a branch, e.g. "dev") is checked out once by the first setup.
# This repository and gpsoauth are never changed, only fetched.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACES="$(dirname "$REPO")"
CORE="$WORKSPACES/home-assistant-core"
GPSOAUTH="$WORKSPACES/gpsoauth"
CONFIG="$CORE/config"
COMPONENT="google_keep_sync"
HA_VENV="$HOME/.venvs/ha"
TEST_VENV="$HOME/.venvs/test"   # a link to $HA_VENV (older setups had a second venv)

HA_CORE_REF="${HA_CORE_REF:-latest}"
HA_CORE_REPO="${HA_CORE_REPO:-https://github.com/home-assistant/core.git}"
GPSOAUTH_REPO="${GPSOAUTH_REPO:-https://github.com/simon-weber/gpsoauth.git}"

UPDATE=0
[[ "${1-}" == "--update" ]] && UPDATE=1

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m==> %s\033[0m\n' "$*"; }

newest_release() {
    git -C "$CORE" tag -l '20*' | grep -E '^[0-9]{4}\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1
}

# The release tag core is on; empty when a branch is checked out (even one
# that points at a release commit) or HEAD is not a tag.
# The release "latest" means: the newest one the test plugin supports
# (ha_requirements.py latest), so the tests run against the Home Assistant you
# run. Without PyPI, the newest release tag.
target_release() {
    python3 "$REPO/.devcontainer/ha_requirements.py" latest 2>/dev/null || newest_release
}

core_tag() {
    git -C "$CORE" symbolic-ref -q HEAD > /dev/null && return 0
    git -C "$CORE" describe --tags --exact-match HEAD 2>/dev/null || true
}

core_clean() {
    [[ -z "$(git -C "$CORE" status --porcelain --untracked-files=no)" ]]
}

# checkout_core <ref> [force]: force only to finish a checkout that was cut
# short (it overwrites the files that one left behind).
checkout_core() {
    git -C "$CORE" -c advice.detachedHead=false checkout --quiet ${2:+--force} "$1"
    log "Home Assistant core: $1 ($(git -C "$CORE" rev-parse --short HEAD))"
}

# Clone, then check out the release. Either step can be cut short (a window
# reload kills setup; the checkout downloads ~30,000 files), so a marker says
# the checkout finished and the next run picks up where the last one stopped.
# A clone stopped before its checkout shows every file as a staged deletion.
clone_core() {
    local done="$CORE/.git/devcontainer-checkout-done"
    [[ -f "$done" ]] && return 0
    if [[ -d "$CORE/.git" ]] && ! git -C "$CORE" rev-parse --quiet --verify HEAD > /dev/null; then
        warn "Home Assistant core clone is incomplete: starting it again"
        find "$CORE" -mindepth 1 -delete
    fi
    if [[ ! -d "$CORE/.git" ]]; then
        log "Cloning Home Assistant core (blobs on demand)"
        git clone --quiet --filter=blob:none --no-checkout "$HA_CORE_REPO" "$CORE"
    elif [[ -z "$(git -C "$CORE" ls-files | head -n 1)" ]] || ! git -C "$CORE" diff --cached --quiet; then
        log "Finishing the Home Assistant core checkout"
    else
        touch "$done"   # a checkout from before the marker existed
        return 0
    fi
    local ref="$HA_CORE_REF"
    [[ "$ref" == "latest" ]] && ref="$(target_release)"
    if ! checkout_core "$ref" force; then
        warn "checkout interrupted or failed; retrying"
        checkout_core "$ref" force
    fi
    touch "$done"
}

# major.minor of a venv's Python, empty if there is none.
venv_python() {
    [[ -x "$1/bin/python" ]] || return 0
    "$1/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])'
}

# Core's venv: the Python core asks for, core in editable mode, its compiled
# translations. Redone only when core's commit or Python changes.
install_core() {
    local python stamp want
    python="$(cat "$CORE/.python-version")"
    stamp="$HA_VENV/.core-installed"
    want="$python $(git -C "$CORE" rev-parse HEAD)"
    [[ -f "$stamp" && "$(cat "$stamp")" == "$want" ]] && return 0
    log "Installing Home Assistant core into $HA_VENV (Python $python)"
    if [[ "$(venv_python "$HA_VENV")" != "$(echo "$python" | cut -d. -f1,2)" ]]; then
        rm -rf "$HA_VENV"
        uv venv --quiet --python "$python" "$HA_VENV"
    fi
    VIRTUAL_ENV="$HA_VENV" uv pip install --quiet -e "$CORE" colorlog \
        --config-settings editable_mode=compat
    (cd "$CORE" && "$HA_VENV/bin/python" -m script.translations develop --all > /dev/null)
    echo "$want" > "$stamp"
}

# The test tools, in the same venv, matched to core's Home Assistant version
# (ha_requirements.py tests). Redone when core or requirements.test.txt change.
install_tests() {
    local req="$REPO/requirements.test.txt" stamp="$HA_VENV/.tests-installed" want ha plan
    ha="$("$HA_VENV/bin/python" -c 'import homeassistant.const as c; print(c.__version__)')"
    want="$ha $(sha256sum "$req" | cut -d' ' -f1)"
    if [[ ! -f "$stamp" || "$(cat "$stamp")" != "$want" ]]; then
        log "Installing the test tools for Home Assistant $ha"
        if plan="$("$HA_VENV/bin/python" "$REPO/.devcontainer/ha_requirements.py" tests "$req" "$ha")" \
            && "$HA_VENV/bin/python" - "$plan" "$HA_VENV" "$ha" <<'PY'
import json, os, subprocess, sys, tempfile
plan, venv, ha = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3]
env = dict(os.environ, VIRTUAL_ENV=venv)
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as pin:
    pin.write(f"homeassistant=={ha}\n")   # keep the editable core checkout
base = ["uv", "pip", "install", "--quiet", "--constraint", pin.name]
subprocess.run(base + plan["requirements"], env=env, check=True)
if plan["no_deps"]:
    subprocess.run(base + ["--no-deps"] + plan["no_deps"], env=env, check=True)
PY
        then
            echo "$want" > "$stamp"
        else
            warn "the test tools did not install; fix requirements.test.txt and run .devcontainer/setup.sh --update"
        fi
    fi
    if [[ -d "$TEST_VENV" && ! -L "$TEST_VENV" ]]; then
        rm -rf "$TEST_VENV"
    fi
    ln -sfn "$HA_VENV" "$TEST_VENV"
}

clone_gpsoauth() {
    [[ -d "$GPSOAUTH/.git" ]] && return 0
    log "Cloning gpsoauth"
    git clone --quiet "$GPSOAUTH_REPO" "$GPSOAUTH"
}

# configuration.yaml (HA's defaults) with debug logging for the integration,
# and the integration linked into custom_components.
setup_config() {
    mkdir -p "$CONFIG/custom_components"
    if [[ ! -f "$CONFIG/configuration.yaml" ]]; then
        "$HA_VENV/bin/hass" --script ensure_config -c "$CONFIG" > /dev/null
    fi
    local yaml="$CONFIG/configuration.yaml"
    if ! grep -q "custom_components.$COMPONENT" "$yaml"; then
        if ! grep -q '^logger:' "$yaml"; then
            printf '\nlogger:\n  default: info\n  logs:\n    custom_components.%s: debug\n' "$COMPONENT" >> "$yaml"
        else
            grep -q '^  logs:' "$yaml" || sed -i '/^logger:/a\  logs:' "$yaml"
            sed -i "/^  logs:/a\\    custom_components.$COMPONENT: debug" "$yaml"
        fi
        log "Debug logging on for custom_components.$COMPONENT"
    fi
    ln -sfn "$REPO/custom_components/$COMPONENT" "$CONFIG/custom_components/$COMPONENT"
}

# The packages of the integrations HA will load (ha_requirements.py), with
# core's version constraints, so a first start or "Home Assistant (skip pip)"
# finds them. Redone when core, configuration.yaml, a manifest or the list
# script changes.
install_requirements() {
    local stamp="$HA_VENV/.requirements-installed" want reqs
    want="$(git -C "$CORE" rev-parse HEAD) $(cat "$REPO/.devcontainer/ha_requirements.py" "$CONFIG/configuration.yaml" "$CONFIG"/custom_components/*/manifest.json 2>/dev/null | sha256sum | cut -d' ' -f1)"
    [[ -f "$stamp" && "$(cat "$stamp")" == "$want" ]] && return 0
    reqs="$("$HA_VENV/bin/python" "$REPO/.devcontainer/ha_requirements.py" integrations "$CORE" "$CONFIG")"
    log "Installing the packages of the integrations Home Assistant loads ($(wc -l <<< "$reqs"))"
    # shellcheck disable=SC2086
    if VIRTUAL_ENV="$HA_VENV" uv pip install --quiet \
        --constraint "$CORE/homeassistant/package_constraints.txt" $reqs; then
        echo "$want" > "$stamp"
    else
        warn "some integration packages did not install; Home Assistant retries at startup (not with skip pip)"
    fi
}

# --update: move core to a newer release when allowed.
update_core() {
    if ! timeout 120 git -C "$CORE" fetch --quiet --tags origin; then
        warn "could not reach $HA_CORE_REPO; Home Assistant core not checked for updates"
        return 0
    fi
    [[ "$HA_CORE_REF" == "latest" ]] || return 0
    local current newest
    current="$(core_tag)"
    newest="$(target_release)"
    if [[ -z "$current" ]]; then
        warn "Home Assistant core is on $(git -C "$CORE" symbolic-ref -q --short HEAD || git -C "$CORE" rev-parse --short HEAD), not a release: not moving it"
    elif ! core_clean; then
        warn "Home Assistant core has local changes: staying on $current (target is $newest)"
    elif [[ "$current" != "$newest" ]]; then
        log "Moving Home Assistant core to $newest (was $current)"
        checkout_core "$newest"
    fi
}

report_repo() {
    timeout 60 git -C "$REPO" fetch --quiet origin 2>/dev/null || return 0
    local upstream behind
    upstream="$(git -C "$REPO" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)" || return 0
    behind="$(git -C "$REPO" rev-list --count "HEAD..$upstream")"
    (( behind > 0 )) && warn "this repository is $behind commit(s) behind $upstream"
    return 0
}

clone_core
(( UPDATE )) && update_core
install_core
clone_gpsoauth
(( UPDATE )) && timeout 60 git -C "$GPSOAUTH" fetch --quiet --all 2>/dev/null
setup_config
install_requirements
install_tests
(( UPDATE )) && report_repo

log "Ready: Home Assistant $(core_tag || true) $(git -C "$CORE" rev-parse --short HEAD) in $CORE"
log "Run it: Run and Debug > \"Home Assistant\", then http://localhost:8123"
