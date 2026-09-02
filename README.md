# ⚡ TOON MCP Server (`toon-mcp`)

**Token-Optimized Object Notation (TOON)** FastMCP Server in Pure Python for efficient AI context management and LLM payload compression.

---

## 🚀 Overview

`toon-mcp` is a lightweight, zero-node Model Context Protocol (MCP) server written entirely in Python. It automatically converts verbose JSON structures into **Token-Optimized Object Notation (TOON)**, achieving up to 60% token reduction in AI agent and tool-call contexts.

> **Credits & Acknowledgments**: TOON format specification and concept inspired by [`aj-geddes/toon-context-mcp`](https://github.com/aj-geddes/toon-context-mcp). This repository provides a native Python port and FastMCP stdio server optimized for Antigravity (AGY) agents, Arch Linux environments, and resource-constrained environments.

---

## ✨ Features

- **35–60% Payload Compression**: Reduces context window consumption on large structured JSON data.
- **Smart Pattern Detection**: Automatically identifies schema patterns, array types, and string redundancies.
- **Key Abbreviation & Reference System**: Automatically abbreviates common keys and deduplicates recurring objects.
- **Pure Python Execution**: Zero Node.js / `node_modules` overhead — executes in under 50ms via standard Python virtualenvs.
- **Lossless Conversion**: Full round-trip conversion (`convert_to_toon` <-> `convert_to_json`).

---

## 🛠️ Installation

### Standard Python Install
```bash
pip install .
```

### Isolated Virtual Environment (Recommended for MCP Agents)
```bash
python3 -m venv ~/.local/share/toon-venv
~/.local/share/toon-venv/bin/pip install -e .
```

---

## 💻 Integration with MCP Clients

Add to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "toon": {
      "command": "/usr/bin/toon-mcp-server",
      "args": []
    }
  }
}
```

---

## 🧰 MCP Tools Provided

- `convert_to_toon`: Converts JSON data into TOON format.
- `convert_to_json`: Restores TOON format back to standard JSON.
- `analyze_patterns`: Analyzes JSON payloads to detect potential compression ratios.
- `get_compression_strategy`: Returns the optimal compression strategy for a given data structure.
- `calculate_savings`: Computes exact character and token savings.
- `batch_convert`: Batch converts lists of JSON objects concurrently.

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
