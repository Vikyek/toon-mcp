# ⚡ TOON MCP Server (`toon-mcp`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Sponsor Vikyek](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?logo=github-sponsors&logoColor=white)](https://github.com/sponsors/Vikyek)

**Token-Optimized Object Notation (TOON)** FastMCP Server and automatic PTY paste wrapper in Pure Python for efficient AI context management and LLM payload compression.

---

## 🚀 Overview

`toon-mcp` is a lightweight, zero-node Model Context Protocol (MCP) server written entirely in Python. It converts verbose JSON structures into **Token-Optimized Object Notation (TOON)**, achieving up to 60% token reduction in AI agent and tool-call contexts, and includes `toon-wrap` to automatically compress JSON pasted into interactive CLI agents before tokens ever reach the model.

> **Credits & Acknowledgments**: TOON format specification and concept inspired by [`aj-geddes/toon-context-mcp`](https://github.com/aj-geddes/toon-context-mcp). This repository provides a native Python port, FastMCP stdio server, and PTY paste-hook wrapper optimized for Antigravity (AGY) agents and Linux environments.

---

## ✨ Features

- **35–60% Payload Compression**: Reduces context window consumption on large structured JSON data.
- **Automatic CLI Paste Hook (`toon-wrap`)**: Transparent PTY bracketed-paste wrapper that converts standalone or embedded JSON in pasted text into TOON before the wrapped CLI receives it.
- **Smart Pattern Detection**: Automatically identifies schema patterns, array types, and string redundancies.
- **Key Abbreviation & Reference System**: Automatically abbreviates common keys and deduplicates recurring objects.
- **Pure Python Execution**: Zero Node.js / `node_modules` overhead — executes in under 50ms via standard Python virtualenvs.
- **Lossless Conversion**: Full round-trip conversion (`convert_to_toon` <-> `convert_to_json`).

---

## 🛠️ Installation

### Quick Install Script

```bash
./install.sh --symlink
```

Use `./install.sh --editable --symlink` during development, or `./install.sh --help` for custom `--venv` and `--bin-dir` paths.

### Manual Installation

1. Create an isolated Python virtual environment:
   ```bash
   python3 -m venv ~/.local/share/toon-venv
   ```
2. Install the package (use `-e .` for editable installs):
   ```bash
   ~/.local/share/toon-venv/bin/pip install .
   ```
3. *(Optional)* Symlink the executables onto your `PATH`:
   ```bash
   mkdir -p ~/.local/bin
   ln -sf ~/.local/share/toon-venv/bin/toon-mcp-server ~/.local/bin/toon-mcp-server
   ln -sf ~/.local/share/toon-venv/bin/toon-wrap ~/.local/bin/toon-wrap
   ```
4. *(Optional)* Install man pages system-wide or locally:
   ```bash
   install -Dm644 man1/toon-mcp.1 ~/.local/share/man/man1/toon-mcp.1
   install -Dm644 man1/toon-wrap.1 ~/.local/share/man/man1/toon-wrap.1
   ```

---

## 💻 Integration

### MCP Clients (`mcp_config.json`)

```json
{
  "mcpServers": {
    "toon": {
      "command": "~/.local/share/toon-venv/bin/toon-mcp-server",
      "args": []
    }
  }
}
```

### Automatic JSON Paste Hook (`toon-wrap`)

Wrap any interactive terminal CLI (such as `agy`) so bracketed pastes containing standalone JSON or embedded JSON blocks are automatically converted to TOON when doing so saves characters:

```bash
toon-wrap -- /usr/bin/agy
```

Example wrapper script at `~/.local/bin/agy`:

```bash
#!/usr/bin/env bash
if [ -t 0 ] && [ -t 1 ] && [ "${TOON_WRAP_DISABLE:-0}" != "1" ]; then
    exec "$HOME/.local/share/toon-venv/bin/toon-wrap" -- /usr/bin/agy "$@"
fi
exec /usr/bin/agy "$@"
```

#### `toon-wrap` Options & Environment Variables

- `--no-aggressive`: Disable domain-key auto-abbreviation (`_custom_keys`).
- `--pure-only`: Only convert pastes whose entire text is valid JSON.
- `--min-chars N`: Minimum JSON block size in characters to convert (default: `60`, or `TOON_WRAP_MIN_CHARS`).
- `TOON_WRAP_DISABLE=1`: Bypass the PTY wrapper and execute the wrapped command directly.
- Non-TTY invocations (piped stdin/stdout) automatically `exec` the target command without opening a PTY.

---

## 🧰 MCP Tools Provided

- `convert_to_toon`: Converts JSON data into TOON format.
- `convert_to_json`: Restores TOON format back to standard JSON.
- `analyze_patterns`: Analyzes JSON payloads to detect potential compression ratios.
- `get_compression_strategy`: Returns the optimal compression strategy for a given data structure.
- `calculate_savings`: Computes exact character and token savings.
- `batch_convert`: Batch converts lists of JSON objects concurrently.

---

## 💖 Support & Sponsorship

`toon-mcp` is developed and maintained independently by **[Vikyek](https://github.com/Vikyek)**. Everything is 100% open-source, telemetry-free, and public.

<div align="center">


[![Sponsor Vikyek](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?logo=github&style=for-the-badge)](https://github.com/sponsors/Vikyek)
[![Donate on Liberapay](https://img.shields.io/badge/Donate-Liberapay-f6c915?style=for-the-badge&logo=liberapay&logoColor=black)](https://liberapay.com/Vikyek)
[![Donate with Stripe](https://img.shields.io/badge/Donate-Stripe-635BFF?style=for-the-badge&logo=stripe&logoColor=white)](https://profile.stripe.com/@vikyek)

</div>

> ### 🎯 Active Sponsorship Goal: Monthly Living Essentials
> **Target:** **2,710 PLN / ~$680 USD per month** (`630 PLN / week`) — Rent & Essential Utilities  
> Covering basic living essentials directly unlocks dedicated, sustainable full-time independent open-source engineering across AI agent middleware and performance utilities free from corporate telemetry, ads, or paywalls.

If `toon-mcp` saves tokens, trims context bloat, or cuts LLM API costs in your workflow, consider supporting ongoing development:

- **GitHub Sponsors**: [github.com/sponsors/Vikyek](https://github.com/sponsors/Vikyek) *(Monthly tiers and one-time tips)*
- **Liberapay**: [liberapay.com/Vikyek](https://liberapay.com/Vikyek) *(0% platform fee recurrent patronage in EUR/USD/PLN)*
- **Direct Stripe Profile**: [profile.stripe.com/@vikyek](https://profile.stripe.com/@vikyek) *(Direct one-time tips & sponsorship)*

Every contribution—monthly or one-time—directly supports active maintenance, hardware testbeds, and new feature development!

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
