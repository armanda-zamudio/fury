FROM ghcr.io/astral-sh/uv:0.9.13 AS uv

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
RUN dnf install cmake python3-devel openssl-devel -y
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv --verbose export --package crimsonking-downloader --frozen --no-emit-workspace --group docker --no-dev -o /requirements.txt && \
    uv --verbose pip install -r /requirements.txt --target /build 

RUN --mount=from=uv,source=/uv,target=/bin/uv \
     --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=packages,target=packages \
    uv export --package crimsonking-downloader --frozen --no-default-groups --no-editable --no-dev -o /requirements.txt && \
    uv pip install --no-deps --no-installer-metadata -r /requirements.txt --target /build --link-mode copy 


# FROM mcr.microsoft.com/playwright/python:v1.55.0-noble AS built    
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble AS built    
SHELL ["/bin/bash", "-c"] 
# RUN --mount=from=uv,source=/uv,target=/bin/uv \
#      --mount=type=cache,target=/root/.cache/uv \
#      uv python install --install-dir /pythons 3.14 && \
#      ln -s $(find /pythons -name python -path '**/bin/**') python
ARG IS_LOCAL
RUN apt-get update
RUN apt-get install poppler-utils ghostscript -y
RUN mkdir -p /app
WORKDIR /app
COPY --from=builder /build /app
COPY packages/crimsonking-cdk/dockerfiles/crimsonking-download-entrypoint.sh /app
RUN \
    find /app -type f ! -perm -644 -exec chmod 644 {} \; && \
    find /app -type d ! -perm -755 -exec chmod 755 {} \;

RUN if [[ -z "$IS_LOCAL" ]] ; then echo Argument not provided ; else apt-get install libnss3-tools unzip jq less -y && \ 
    mkdir -p /.aws-lambda-rie && curl -Lo /.aws-lambda-rie/aws-lambda-rie \
    https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie && \ 
    chmod +x /.aws-lambda-rie/aws-lambda-rie && \
    ARCH=`arch` && \
    if [[ "$ARCH" == "x86_64" ]] ; then curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/awscliv2.zip" ; \
    else curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "/awscliv2.zip" ; fi && \
    cd / && unzip awscliv2.zip &&  \
    /aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update && \
    rm /awscliv2.zip && rm -rf /aws  && \
    pip install awscli-local ; fi    
FROM built AS final
# Install python with uv, and make a symbolic link at /python to it.
RUN --mount=from=uv,source=/uv,target=/bin/uv \
     --mount=type=cache,target=/root/.cache/uv \
     uv python install --install-dir /pythons 3.14 && \
     rm /usr/bin/python && \
     ln -s $(find /pythons -name python -path '**/bin/**')  /usr/bin/python 
COPY packages/ih/src /app
COPY packages/crimsonking/src /app
COPY packages/crimsonking-downloader/src /app
RUN \
    find /app -type f ! -perm -644 -exec chmod 644 {} \; && \
    find /app -type d ! -perm -755 -exec chmod 755 {} \;  
RUN chmod +x /app/crimsonking-download-entrypoint.sh    
ENTRYPOINT [ "./crimsonking-download-entrypoint.sh" ]    

# ENTRYPOINT ["bash", "-c", "sleep infinity"]
