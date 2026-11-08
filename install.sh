#!/usr/bin/env bash
set -euo pipefail

# Idempotent installer for toon-mcp (toon-mcp-server + toon-wrap).

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${TOON_VENV_DIR:-$HOME/.local/share/toon-venv}"
BIN_DIR="${TOON_BIN_DIR:-$HOME/.local/bin}"
EDITABLE=0
SYMLINK_BINS=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Install toon-mcp-server and toon-wrap into an isolated Python virtualenv.

Options:
  --venv DIR      Target virtualenv path (default: $VENV_DIR)
  --bin-dir DIR   Target bin directory when --symlink is passed (default: $BIN_DIR)
  -e, --editable  Install package in editable mode
  --symlink       Symlink toon-mcp-server and toon-wrap into --bin-dir
  -h, --help      Show this help message and exit
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --venv)
            VENV_DIR="$2"
            shift 2
            ;;
        --bin-dir)
            BIN_DIR="$2"
            shift 2
            ;;
        -e|--editable)
            EDITABLE=1
            shift
            ;;
        --symlink)
            SYMLINK_BINS=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ ! -x "$VENV_DIR/bin/python3" ]; then
    echo "Creating virtualenv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo "Using existing virtualenv at $VENV_DIR."
fi

echo "Installing toon-mcp from $REPO_DIR..."
if [ "$EDITABLE" -eq 1 ]; then
    "$VENV_DIR/bin/pip" install --upgrade -e "$REPO_DIR"
else
    "$VENV_DIR/bin/pip" install --upgrade "$REPO_DIR"
fi

if [ "$SYMLINK_BINS" -eq 1 ]; then
    mkdir -p "$BIN_DIR"
    ln -sf "$VENV_DIR/bin/toon-mcp-server" "$BIN_DIR/toon-mcp-server"
    ln -sf "$VENV_DIR/bin/toon-wrap" "$BIN_DIR/toon-wrap"
    echo "Symlinked binaries into $BIN_DIR."
fi

cat <<EOF

Installation complete:
  MCP server : $VENV_DIR/bin/toon-mcp-server
  Paste hook : $VENV_DIR/bin/toon-wrap

Optional CLI paste-hook wrapper (~/.local/bin/agy):
  if [ -t 0 ] && [ -t 1 ] && [ "\${TOON_WRAP_DISABLE:-0}" != "1" ]; then
      exec "$VENV_DIR/bin/toon-wrap" -- /usr/bin/agy "\$@"
  fi
  exec /usr/bin/agy "\$@"
EOF
