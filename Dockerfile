FROM python:3.12-slim

# Installer curl
RUN apt-get update && apt-get install -y curl && apt-get clean
RUN apt-get update && apt-get install -y git && apt-get clean
RUN apt-get update && apt-get install -y iputils-ping
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    gcc \
    cmake \
    make \
    libpq-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

# install ffmpeg
RUN apt update && \
    apt install -y ffmpeg 

# Set environment variables for Hugging Face cache location
ENV XDG_CACHE_HOME=${XDG_CACHE_HOME:-/app/model_weights}
ENV HF_HOME=${HF_HOME:-/app/model_weights}
ENV HF_HUB_CACHE=${HF_HUB_CACHE:-/app/model_weights/hub}

# Set workdir for uv
WORKDIR /app

# Accept build argument for version
ARG SETUPTOOLS_SCM_PRETEND_VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}

# Install uv & setup venv
COPY pyproject.toml uv.lock ./
RUN pip3 install uv && \
    uv python install 3.12.7 && \
    uv python pin 3.12.7 && \
    uv sync --no-dev
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
# Set workdir for source code
WORKDIR /app/openrag

# Copy source code
COPY openrag/ .

# Copy assests & config
COPY public/ /app/public/
COPY prompts/ /app/prompts/
COPY .hydra_config/ /app/.hydra_config/
ENV PYTHONPATH=/app/openrag/
ENV APP_iPORT=${APP_iPORT:-8080}
ENTRYPOINT ../entrypoint.sh
