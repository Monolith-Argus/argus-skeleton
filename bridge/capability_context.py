"""Read capability-memory rules for system-prompt injection.

``capability-memory/*.md`` holds operating rules versioned in this repository.
This module concatenates them (newest first, up to a soft byte cap) so
``docker/entrypoint.sh`` can prepend the result to every task's system prompt.
Run as a script to emit the block on stdout.
"""
from __future__ import annotations

import os
from pathlib import Path

# Where the rules live inside the task container (see Dockerfile COPY).
CAP_DIR = Path(os.environ.get("ARGUS_CAPABILITY_DIR", "/opt/argus/capability-memory"))
SOFT_CAP_BYTES = 24_000


def render() -> str:
    if not CAP_DIR.is_dir():
        return ""
    files = sorted(CAP_DIR.rglob("*.md"))
    if not files:
        return ""

    parts: list[str] = [
        "[CAPABILITY MEMORY — operating rules shipped with this repo]",
    ]
    used = 0
    for f in files:
        if f.name.upper() in {"README.MD", "MANIFEST.MD"}:
            continue
        try:
            body = f.read_text().strip()
        except OSError:
            continue
        chunk = f"\n## {f.stem}\n\n{body}"
        if used + len(chunk) > SOFT_CAP_BYTES:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n".join(parts)


if __name__ == "__main__":
    out = render()
    if out:
        print(out)
