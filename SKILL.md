---
name: toon-mcp
description: >-
  Token-Optimized Object Notation (TOON) compression guide and MCP workflow for
  cutting JSON payload token spend by 35-60% in AI agents (Claude Code, Cursor,
  Copilot, Antigravity, Codex). Teaches agents when and how to call `toon` MCP
  tools (`convert_to_toon`, `convert_to_json`, `analyze_patterns`,
  `get_compression_strategy`, `calculate_savings`, `batch_convert`) and wrap
  interactive CLIs with `toon-wrap`.
version: 1.0.0
summary: >-
  Cut JSON token spend 35-60% with lossless TOON compression via FastMCP and
  automatic PTY paste wrapping (`toon-wrap`).
tags:
  - llm-ops
  - workflow-automation
  - apis-backend
  - data-databases
keywords:
  - toon
  - mcp
  - json
  - compression
  - token-optimization
  - context-window
  - fastmcp
  - toon-wrap
use_cases:
  - Compressing large JSON API responses, database rows, or tool outputs before passing them into agent context
  - Losslessly round-tripping TOON payloads back to strict JSON before writing manifests or making API calls
  - Estimating token and character savings before serializing large structured datasets
  - Wrapping interactive AI coding CLIs with `toon-wrap` to auto-compress pasted JSON blocks
---

# TOON MCP Skill (`toon-mcp`)

Use this skill whenever handling structured JSON payloads, API responses, log dumps, or multi-record datasets where context-window tokens matter.

## When to Activate

Activate this skill when:
- Importing, passing, or storing structured JSON payloads larger than ~60 characters.
- Working with arrays of uniform objects, API responses, or tabular records.
- Needing lossless round-trip restoration from TOON back to strict JSON.
- Wrapping interactive CLI agents (`agy`, `claude`, `codex`, `aider`) with `toon-wrap` to compress pasted JSON automatically.

Skip TOON conversion when:
- Editing exact JSON manifest files in place (e.g., `package.json`, `tsconfig.json`, `mcp_config.json`).
- Handling credential-bearing JSON files (never pass plaintext secrets into tool arguments; redact first).
- Payloads are tiny (<60 chars) where header metadata would exceed savings.

## MCP Tools

Connect the `toon-mcp-server` stdio MCP server (see `README.md` for `mcp_config.json`), then use:

| Tool | Required Args | Optional Args | Purpose |
|------|---------------|---------------|---------|
| `convert_to_toon` | `json_data` (string) | `aggressive` (bool, default `false`) | Convert JSON into compact TOON format |
| `convert_to_json` | `toon_data` (string) | — | Losslessly restore TOON back to JSON |
| `analyze_patterns` | `json_data` (string) | — | Inspect schema patterns and compression potential |
| `get_compression_strategy` | `json_data` (string) | — | Get recommended compression settings for payload shape |
| `calculate_savings` | `json_data` (string) | — | Measure exact character and estimated token savings |
| `batch_convert` | `json_array` (string) | `aggressive` (bool, default `false`) | Convert a JSON array of objects in one call |

## Recommended Agent Workflow

1. **Assess large or unfamiliar payloads**: Call `get_compression_strategy(json_data=...)` or `analyze_patterns(json_data=...)` to check whether tabular/schema compression applies.
2. **Compress for context**: Call `convert_to_toon(json_data=...)`. Set `aggressive=true` to enable domain-key auto-abbreviation (`_custom_keys`) when maximum token savings are desired; keep `aggressive=false` when literal key names are preferred.
3. **Batch records**: For lists of objects, use `batch_convert(json_array=...)` instead of looping single calls.
4. **Restore exact JSON**: Before writing strict JSON files or calling external JSON APIs, call `convert_to_json(toon_data=...)` to restore the original structure losslessly.
5. **Verify savings**: Use `calculate_savings(json_data=...)` when reporting token/character reduction metrics.

## Interactive CLI Paste Wrapper (`toon-wrap`)

For terminal-based AI CLIs, `toon-wrap` intercepts bracketed pastes over a PTY and converts standalone or embedded JSON blocks (`>= 60` chars by default) into TOON before the CLI reads them:

```bash
toon-wrap -- /usr/bin/agy
toon-wrap --no-aggressive --min-chars 100 -- claude
```

- Set `TOON_WRAP_DISABLE=1` to bypass wrapping without changing shell wrappers.
- Non-TTY invocations (`stdin`/`stdout` piped) automatically `exec` the target command directly.

## Requirements & Setup

- **Runtime**: Python 3.10+ with `mcp>=0.9.0` (no Node.js required).
- **Install**: `./install.sh --symlink` (or `pip install .` inside `~/.local/share/toon-venv`).
- **Executables**: `toon-mcp-server` (stdio MCP server) and `toon-wrap` (PTY paste hook).
