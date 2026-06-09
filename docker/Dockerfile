FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    NODE_VERSION=20 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin:/root/.fly/bin

# Base toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg git openssh-client \
        build-essential pkg-config \
        python3 python3-pip python3-venv \
        ripgrep jq sqlite3 less unzip zip xz-utils sudo && \
    rm -rf /var/lib/apt/lists/*

# Node 20 (NodeSource)
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod 644 /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | tee /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

# Python packages used on the bridge side (classifier/router). slack-bolt and
# pytest are included so bridge modules import cleanly inside the container.
RUN python3 -m pip install --break-system-packages --no-cache-dir \
        anthropic httpx requests pyyaml slack-bolt slack-sdk pytest

# Claude Code CLI + a couple of deploy CLIs.
RUN npm install -g @anthropic-ai/claude-code vercel

# Fly.io CLI
RUN curl -fsSL https://fly.io/install.sh | sh

# A non-root user for the agent.
RUN useradd -ms /bin/bash agent && \
    mkdir -p /workspace && chown -R agent:agent /workspace

# Bridge modules, capability memory, and schema are baked into the image so the
# entrypoint can import bridge.* and inject capability-memory into the prompt.
RUN mkdir -p /opt/argus
COPY bridge/ /opt/argus/bridge/
COPY capability-memory /opt/argus/capability-memory
COPY migrations /opt/argus/migrations

ENV PYTHONPATH=/opt/argus \
    DB_PATH=/host/state/argus.db

WORKDIR /workspace

COPY docker/entrypoint.sh /usr/local/bin/argus-entrypoint
RUN chmod +x /usr/local/bin/argus-entrypoint

ENTRYPOINT ["/usr/local/bin/argus-entrypoint"]
