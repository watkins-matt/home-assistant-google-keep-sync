# Dev container for Google Keep Sync: Home Assistant core from source plus this
# integration. System packages follow Home Assistant core's own Dockerfile.dev.
# The image's Python is there from the first second, so VS Code finds an
# interpreter before setup has run; the venvs (.devcontainer/setup.sh) use the
# exact version core asks for, through uv.
FROM mcr.microsoft.com/devcontainers/python:3.14

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        autoconf \
        bluez \
        cmake \
        ffmpeg \
        git \
        libavcodec-dev \
        libavdevice-dev \
        libavfilter-dev \
        libavformat-dev \
        libavutil-dev \
        libpcap-dev \
        libswresample-dev \
        libswscale-dev \
        libturbojpeg0 \
        libudev-dev \
        libxml2 \
        libyaml-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
# Home Assistant's go2rtc integration (in default_config) needs this binary
# when it runs in a container, as core's own Dockerfile.dev provides it.
COPY --from=ghcr.io/alexxit/go2rtc:latest /usr/local/bin/go2rtc /bin/go2rtc

# The workspace is a bind mount owned by another uid (git calls it "dubious
# ownership"). Set system-wide, so nothing writes ~/.gitconfig before VS Code
# copies yours (name, email, credentials) in; it skips that when one exists.
RUN git config --system --add safe.directory '*'

# Mount points of the named volumes (devcontainer.json). Created here, owned by
# vscode, so each new volume starts out writable by vscode.
RUN mkdir -p /workspaces/home-assistant-core /workspaces/gpsoauth /home/vscode/.venvs \
    && chown vscode:vscode /workspaces/home-assistant-core /workspaces/gpsoauth /home/vscode/.venvs

USER vscode
ENV UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/home/vscode/.venvs/python
