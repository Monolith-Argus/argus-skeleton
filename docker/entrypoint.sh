#!/usr/bin/env bash
# Argus task container entrypoint.
# - Verifies Claude Code OAuth auth (fail-fast).
# - Configures git auth + identity.
# - Clones the requested repo into /workspace.
# - Runs `claude` in headless stream-json mode with the user's prompt.
set -euo pipefail

PROMPT="${*:-}"
if [[ -z "${PROMPT}" ]]; then
    echo '{"type":"result","subtype":"error","is_error":true,"result":"empty prompt"}' >&2
    exit 2
fi

# --- Claude Code auth (fail-fast) ---
# The OAuth token is the only auth path for task inference. The Anthropic API
# key is reserved for the bridge-side classifier/router; we do not fall back to
# it here. When both are present, rename the API key so the agent's SDK can't
# auto-detect it and bill per-token.
if [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    export CLAUDE_CODE_OAUTH_TOKEN
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        export ARGUS_ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"
        unset ANTHROPIC_API_KEY
    fi
else
    cat <<'JSON'
{"type":"result","subtype":"error","is_error":true,"result":"Task refused: CLAUDE_CODE_OAUTH_TOKEN is not set. This is the only auth path for task inference; the Anthropic API key is reserved for the bridge-side classifier/router. Set CLAUDE_CODE_OAUTH_TOKEN and retry."}
JSON
    exit 4
fi

# Establish a writable HOME (we run as a non-root UID without a passwd entry).
export HOME="${HOME:-/tmp/argus-home}"
mkdir -p "$HOME"
cd "$HOME" 2>/dev/null || true

# Container isolation is the security boundary; there is no human at a terminal
# to approve in-tool permission prompts, so bypass them.
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/settings.json" <<'SETTINGS_JSON'
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
SETTINGS_JSON

# --- git identity & auth ---
# Point git's global config at a per-container path under /tmp so concurrent
# containers sharing $HOME never race on the gitconfig lockfile.
export GIT_CONFIG_GLOBAL="/tmp/argus-git/gitconfig"
GIT_LOCAL_DIR="$(dirname "$GIT_CONFIG_GLOBAL")"
mkdir -p "$GIT_LOCAL_DIR"
: > "$GIT_CONFIG_GLOBAL"

[[ -n "${GITHUB_USER:-}" ]] && git config --global user.name "${GITHUB_USER}"
[[ -n "${GITHUB_EMAIL:-}" ]] && git config --global user.email "${GITHUB_EMAIL}"

# Credential helper emits the token, keeping it out of remote URLs.
cat > "$GIT_LOCAL_DIR/credentials-helper.sh" <<EOF
#!/usr/bin/env bash
echo "username=${GITHUB_USER:-x-access-token}"
echo "password=${GITHUB_TOKEN:-}"
EOF
chmod +x "$GIT_LOCAL_DIR/credentials-helper.sh"
git config --global credential.helper "$GIT_LOCAL_DIR/credentials-helper.sh"
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    echo "${GITHUB_TOKEN}" | gh auth login --with-token >/dev/null 2>&1 || true
fi

# --- vendor CLI auth ---
[[ -n "${VERCEL_TOKEN:-}" ]] && export VERCEL_TOKEN
[[ -n "${FLY_API_TOKEN:-}" ]] && export FLY_API_TOKEN

# --- repo clone ---
WORK_DIR="/workspace"
if [[ -n "${REPO:-}" ]]; then
    if ! [[ "${REPO}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
        cat <<JSON
{"type":"result","subtype":"error","is_error":true,"result":"Task refused: REPO must be 'org/name', got '${REPO}'."}
JSON
        exit 3
    fi
    REPO_DIR="/workspace/$(basename "${REPO}")"
    if [[ -d "${REPO_DIR}/.git" ]]; then
        git -C "${REPO_DIR}" fetch --all >&2 || true
        git -C "${REPO_DIR}" pull --ff-only >&2 || \
            git -C "${REPO_DIR}" reset --hard origin/HEAD >&2 || true
    else
        rm -rf "${REPO_DIR}"
        if ! git clone "https://github.com/${REPO}.git" "${REPO_DIR}" >&2; then
            echo "clone failed for ${REPO}; starting with an empty workspace" >&2
            mkdir -p "${REPO_DIR}"
            git -C "${REPO_DIR}" init -q -b main >&2 || true
        fi
    fi
    WORK_DIR="${REPO_DIR}"
fi
cd "${WORK_DIR}"

# --- run parameters ---
THINK_FLAGS=()
case "${ARGUS_THINKING:-medium}" in
    off) ;;
    low)    THINK_FLAGS+=(--max-thinking-tokens 4000) ;;
    medium) THINK_FLAGS+=(--max-thinking-tokens 16000) ;;
    high)   THINK_FLAGS+=(--max-thinking-tokens 32000) ;;
esac
MAX_ITER="${ARGUS_MAX_ITERATIONS:-60}"
MODEL="${ARGUS_MODEL:-claude-sonnet-4-6}"

# --- identity primer ---
# Appended to the system prompt every run. The deeper context lives in CLAUDE.md
# in the repo this agent operates on.
IDENTITY=$(cat <<'EOF'
You are Argus, a Slack-driven coding agent. You run on the Claude Code CLI inside
an ephemeral container spawned per message; you are not the CLI itself.

Your own source tree is one of your memory layers. When a request asks to change
how you route, classify, schedule, or format output, that means editing the Argus
codebase (bridge/, scheduler/, docker/, capability-memory/) on a branch and
opening a pull request — behavior persists by being committed, not by being held
in a database. You cannot modify the Claude Code binary; it ships in your image.

/workspace and HOME persist across containers; everything else is fresh per task.
EOF
)

# --- intent notice ---
if [[ -n "${ARGUS_INTENT:-}" ]]; then
    IDENTITY="${IDENTITY}

[INTENT] The bridge classified this message as: ${ARGUS_INTENT}"
fi

# --- capability memory injection ---
# Read /opt/argus/capability-memory/*.md and prepend the operating rules to the
# system prompt. Never blocks task start.
CAPABILITY_CTX="$(timeout 5 python3 -m bridge.capability_context 2>/dev/null || true)"
if [[ -n "${CAPABILITY_CTX}" ]]; then
    IDENTITY="${IDENTITY}

${CAPABILITY_CTX}"
fi

# --- autonomous vs interactive guidance ---
if [[ "${ARGUS_AUTONOMOUS:-}" == "1" ]]; then
    IDENTITY="${IDENTITY}

[AUTONOMOUS MODE] You are a scheduled job with no human attached. Do not ask
clarifying questions or pause for confirmation. Make the best decision with the
information available, execute end-to-end, and produce a complete result. If a
step fails, note it in your final summary and proceed with what you can do."
else
    IDENTITY="${IDENTITY}

[INTERACTIVE MODE] A human is on Slack. Given a clear directive, execute it
end-to-end without checking back. Reserve clarifying questions for genuinely
ambiguous requests or actions that cannot be undone."
fi

exec claude \
    --print \
    --output-format stream-json \
    --verbose \
    --model "${MODEL}" \
    --max-turns "${MAX_ITER}" \
    --dangerously-skip-permissions \
    --append-system-prompt "${IDENTITY}" \
    "${THINK_FLAGS[@]}" \
    "${PROMPT}"
