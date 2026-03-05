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

RUN mkdir -p /asset/python
RUN mkdir /tmp_asset




RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv --verbose export --package fury --frozen --no-emit-workspace -o /requirements.txt && \
    uv --verbose pip install -r /requirements.txt --target /tmp_asset

RUN mv /tmp_asset/pandas*   /asset/python/
RUN mv /tmp_asset/xlsxwriter*   /asset/python/
RUN mv /tmp_asset/numpy*   /asset/python/
RUN mv /tmp_asset/pytz*   /asset/python/
RUN mv /tmp_asset/tzdata*   /asset/python/
RUN rm -rf /tmp_asset

RUN ls /asset/python

