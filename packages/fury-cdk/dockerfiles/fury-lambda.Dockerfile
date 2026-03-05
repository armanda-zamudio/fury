FROM ghcr.io/astral-sh/uv:0.9.9 AS uv

# First, bundle the dependencies into the task root.
FROM public.ecr.aws/lambda/python:3.14 AS builder

# Enable bytecode compilation, to improve cold-start performance.
ENV UV_COMPILE_BYTECODE=1

# Disable installer metadata, to create a deterministic layer.
ENV UV_NO_INSTALLER_METADATA=1

# Enable copy mode to support bind mount caching.
ENV UV_LINK_MODE=copy

# Use bash for the shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Bundle the dependencies into the Lambda task root via `uv pip install --target`.
#
# Omit any local packages (`--no-emit-workspace`) and development dependencies (`--no-dev`).
# This ensures that the Docker layer cache is only invalidated when the `pyproject.toml` or `uv.lock`
# files change, but remains robust to changes in the application code.

RUN mkdir /asset


RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv --verbose export --package fury --frozen --no-emit-workspace --no-dev -o /requirements.txt && \
    uv --verbose pip install -r /requirements.txt --target /asset

RUN --mount=from=uv,source=/uv,target=/bin/uv \
     --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=packages,target=packages \
    uv export --package fury --frozen --no-default-groups --no-editable --no-dev -o /requirements.txt && \
    uv pip install --no-deps --no-installer-metadata -r /requirements.txt --target /asset --link-mode copy


