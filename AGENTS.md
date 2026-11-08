# Agent Guidelines

## Commit & Git Conventions
When completing tasks and committing changes, follow these strict rules to format your commit descriptions:

1. **Enforce the Imperative Mood and Brevity**:
   - Start the subject line with an imperative verb (e.g., `fix`, `add`, `remove`, `refactor`).
   - Keep the subject line under 72 characters.
   - Never use robotic preambles like *"This commit modifies..."* or *"Successfully updated..."*.

2. **Focus on the "Why" Instead of the "What"**:
   - Explain the motivation behind the change. Why was the fix/feature necessary? What problem does it solve?

3. **Developer-Friendly Structure**:
   - Use a short summary paragraph first, followed by bullet points for technical details.
   - Keep the tone professional, concise, and clear.

## Reference Commit Style
Below are examples of commit messages written by the developer in this repository. Analyze these examples to understand and imitate the preferred writing style, tone, level of detail, and formatting:

```gitcommit
fix(ci): add continue-on-error to CodeQL analyze for private repos

---
fix(ci): check GPG_PRIVATE_KEY secret in sign-jules-commits

---
build(aur): add PKGBUILD, .SRCINFO, and update docs for v1.0.0 release

---
ci: add GitHub Actions workflows for secret scanning, CodeQL, and commit signing

---
feat(toon-mcp): initialize repository with toon mcp server codebase
```

## Project Structure & Documentation Parity
This repository exposes two primary CLI entrypoints:
- `toon-mcp-server`: Pure Python FastMCP stdio server (`src/server.py`).
- `toon-wrap`: Transparent PTY bracketed-paste JSON-to-TOON compressor (`src/paste_wrapper.py`).

Whenever introducing changes:
1. **CLI Parity**: Verify `-h`/`--help` and `-V`/`--version` execute cleanly on both `toon-mcp-server` and `toon-wrap`.
2. **Manpages**: Keep `man1/toon-mcp.1` and `man1/toon-wrap.1` synced with all CLI flags and behaviors.
3. **Packaging**: Keep `PKGBUILD` and `.SRCINFO` synced (`makepkg --printsrcinfo > .SRCINFO`).
4. **Docs & Installers**: Ensure `README.md` and `install.sh` reflect any added tools or arguments.
5. **Verification**: Run `pytest -v tests/` before committing.
