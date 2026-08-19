# Dayo Notes Writer: Agent Instructions

**Context:** You are working on Dayo Notes Writer, a local, ephemeral MCP-powered note transformation utility.

## Environment: WSL-First (Strict)
- **Execution:** All terminal commands, `python`, `git`, and build tools **must** execute inside the WSL Linux distribution. Never assume Windows PowerShell or Windows paths.
- **Package Manager:** Use `uv` exclusively (e.g., `~/.local/bin/uv run`, `uv pip install`).
- **Line Endings:** Generate files with **LF** only (no CRLF).
- **Paths:** Use native Linux paths (`~/projects/dayo-notes-writer`). Avoid `/mnt/c/` for heavy operations.

## Architecture: Core Boundaries
- **Strict Separation:** The application owns the structure and persistence (path, filename, storage resolution). The LLM owns **only** the content generation (title, body, tags). The LLM must never decide final filesystem paths.
- **Deep Modules:** Design the application core as a deterministic, interface-agnostic module. The MCP server and CLI are just adapters sitting at the external seam.
- **Pydantic Validation:** All LLM output must be validated through a Pydantic `NoteDraft` model before hitting the Markdown renderer.

## Context Pointers
- **Project Knowledge Base:** For architecture, design decisions, and scope, read: [project-knowledge.md](file:///\\wsl.localhost\Ubuntu\home\phen\projects\dayo-notes-writer\docs\project-knowledge.md)
- **Domain Language:** (To be created in `CONTEXT.md` as domain terms crystallise).
