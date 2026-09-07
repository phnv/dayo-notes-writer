"""
Dayo Notes Writer — Agent Interface (Milestone 4b)

This module implements the mcp-agent + MCP client layer.
It spawns the Dayo MCP server as a stdio subprocess and connects an LLM
(OpenAI or Gemini) to orchestrate note write/update operations.

Entry point: `note-writer` CLI command (see pyproject.toml).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.config import (
    Settings,
    LoggerSettings,
    MCPSettings,
    MCPServerSettings,
    OpenAISettings,
    GoogleSettings,
)
from mcp_agent.elicitation.handler import console_elicitation_callback
from mcp_agent.human_input.console_handler import console_input_callback

# Load .env early so pydantic-settings can read API keys
load_dotenv()

# ---------------------------------------------------------------------------
# Provider type
# ---------------------------------------------------------------------------
Provider = Literal["openai", "gemini"]

# ---------------------------------------------------------------------------
# Inline agent system instruction
# ---------------------------------------------------------------------------
_AGENT_INSTRUCTION = """\
You are the Dayo Notes Writer agent. Your job is to help the user create and update
well-structured Markdown notes saved to their configured storage locations.

You have access to the Dayo MCP server tools:
  - list_templates: list available note templates
  - list_storages: list available storage aliases
  - list_bundles: list available configuration bundles
  - read_note: read an existing note
  - save_note: write a new note to disk (requires: content, template, storage, filename)
  - update_note: append content to an existing note

Workflow for writing a new note:
1. If all arguments (raw_text, template, storage) are provided, proceed immediately.
2. If arguments are missing, use list_templates / list_storages to discover options and
   guide the user. Do NOT invent template or storage names.
3. Call save_note only when you have confirmed: content, template path or alias,
   storage alias or path, and a reasonable filename.
4. Report the saved file path to the user when done.

Workflow for updating a note:
1. If file_name and storage are provided, call update_note directly.
2. If missing, ask the user for the required details.

Always use the MCP tools — never generate filesystem paths yourself.
The server owns path resolution and file persistence.
"""

# ---------------------------------------------------------------------------
# Settings builder
# ---------------------------------------------------------------------------

def _resolve_project_root() -> Path:
    """Resolve the project root from env var or from this file's location."""
    env_root = os.environ.get("NOTE_WRITER_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    # Fallback: interfaces/ → note_writer/ → src/ → project root
    return Path(__file__).parent.parent.parent.parent

def _build_settings(provider: Provider) -> Settings:
    """Build programmatic mcp-agent Settings with the Dayo MCP server wired in."""
    project_root = _resolve_project_root()
    repo_root = Path(__file__).parent.parent.parent.parent
    uv_path = os.environ.get("UV_PATH", "/home/phen/.local/bin/uv")

    # The MCP server is launched as a stdio subprocess from the project root.
    mcp_server = MCPServerSettings(
        command=uv_path,
        args=["run", "note-writer-mcp"],
        env={"NOTE_WRITER_PROJECT_ROOT": str(project_root)},
        cwd=str(repo_root),
    )

    # Provider-specific settings are read from .env via pydantic-settings.
    # We only set the model defaults here; API keys come from environment.
    openai_settings = OpenAISettings(default_model="gpt-4o")
    google_settings = GoogleSettings(default_model="gemini-2.0-flash")

    return Settings(
        execution_engine="asyncio",
        logger=LoggerSettings(transports=["console"], level="warning"),
        mcp=MCPSettings(servers={"dayo-notes-writer": mcp_server}),
        openai=openai_settings,
        google=google_settings,
    )


def _get_llm_class(provider: Provider):
    """Return the AugmentedLLM class for the given provider."""
    if provider == "openai":
        from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM  # noqa: PLC0415
        return OpenAIAugmentedLLM
    elif provider == "gemini":
        from mcp_agent.workflows.llm.augmented_llm_google import GoogleAugmentedLLM  # noqa: PLC0415
        return GoogleAugmentedLLM
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Choose 'openai' or 'gemini'.")


async def _print_usage(token_counter, provider: Provider) -> None:
    """Print a compact token usage + cost summary to stderr after a run.

    Uses mcp-agent's built-in TokenCounter (Option 1).
    Gemini degrades gracefully because GoogleAugmentedLLM does not call
    record_usage() in the current version — no data will be recorded.

    Future: add Gemini support via tokencost (Option 2 — documented in
    docs/token-tracking.md, not yet implemented).
    """
    sep = "─" * 44
    print(f"\n{sep}", file=sys.stderr)
    print("  token usage", file=sys.stderr)

    try:
        summary = await token_counter.get_summary()
        total = summary.usage

        if total.total_tokens == 0:
            # No data recorded — expected for Gemini (record_usage not wired).
            if provider == "gemini":
                print(
                    "  [gemini token tracking not wired yet — cost: n/a]",
                    file=sys.stderr,
                )
            else:
                print("  [no token data recorded]", file=sys.stderr)
        else:
            print(
                f"  in: {total.input_tokens:,}  "
                f"out: {total.output_tokens:,}  "
                f"total: {total.total_tokens:,}",
                file=sys.stderr,
            )

            # Per-model breakdown (each LLM call / iteration)
            if summary.model_usage:
                for model_key, model_summary in summary.model_usage.items():
                    mu = model_summary.usage
                    print(
                        f"  {model_key}:  "
                        f"in {mu.input_tokens:,}  /  out {mu.output_tokens:,}",
                        file=sys.stderr,
                    )

            # Estimated cost
            cost = summary.cost
            print(f"  estimated cost: ~${cost:.4f}", file=sys.stderr)

    except Exception as exc:  # noqa: BLE001
        print(f"  [token tracking error: {exc}]", file=sys.stderr)

    print(sep, file=sys.stderr)


# ---------------------------------------------------------------------------
# Agent operations
# ---------------------------------------------------------------------------

async def run_write_note(
    raw_text: str,
    *,
    template: str | None = None,
    storage: str | None = None,
    bundle: str | None = None,
    filename: str | None = None,
    provider: Provider = "openai",
) -> str:
    """
    Run the write-note agent flow:
    1. Connect to the Dayo MCP server.
    2. Fetch the write_note MCP prompt (server injects template + instructions).
    3. Ask the LLM to reason and call save_note when ready.
    4. Return the final LLM response string.
    """
    settings = _build_settings(provider)
    llm_class = _get_llm_class(provider)

    app = MCPApp(
        name="dayo-notes-writer",
        settings=settings,
        elicitation_callback=console_elicitation_callback,
        human_input_callback=console_input_callback,
    )

    async with app.run() as running_app:
        agent = Agent(
            name="dayo-writer",
            instruction=_AGENT_INSTRUCTION,
            server_names=["dayo-notes-writer"],
        )
        async with agent:
            llm = await agent.attach_llm(llm_class)

            # Build prompt arguments — omit None values so server uses bundle defaults
            prompt_args: dict[str, str] = {"raw_text": raw_text}
            if template:
                prompt_args["template"] = template
            if storage:
                prompt_args["storage"] = storage
            if bundle:
                prompt_args["bundle"] = bundle

            # Fetch the write_note MCP prompt from the server.
            # The server returns: system_prompt + prompt instructions + template + raw_text
            prompt_result = await agent.get_prompt(
                "write_note",
                arguments=prompt_args,
                server_name="dayo-notes-writer",
            )

            if not prompt_result.messages:
                raise RuntimeError("MCP server returned an empty write_note prompt.")

            # Hand the assembled messages to the LLM.
            # The agent will call save_note (and other tools) as needed.
            response = await llm.generate_str(
                message=prompt_result.messages,
            )

        await _print_usage(running_app.context.token_counter, provider)
        return response


async def run_update_note(
    append_text: str,
    *,
    file_name: str | None = None,
    storage: str | None = None,
    bundle: str | None = None,
    provider: Provider = "openai",
) -> str:
    """
    Run the update-note agent flow:
    1. Connect to the Dayo MCP server.
    2. Fetch the update_note MCP prompt.
    3. Ask the LLM to call update_note tool.
    4. Return the final response string.
    """
    settings = _build_settings(provider)
    llm_class = _get_llm_class(provider)

    app = MCPApp(
        name="dayo-notes-writer",
        settings=settings,
        elicitation_callback=console_elicitation_callback,
        human_input_callback=console_input_callback,
    )

    async with app.run() as running_app:
        agent = Agent(
            name="dayo-updater",
            instruction=_AGENT_INSTRUCTION,
            server_names=["dayo-notes-writer"],
        )
        async with agent:
            llm = await agent.attach_llm(llm_class)

            prompt_args: dict[str, str] = {"raw_text": append_text}
            if file_name:
                prompt_args["file_name"] = file_name
            if storage:
                prompt_args["storage"] = storage
            if bundle:
                prompt_args["bundle"] = bundle

            prompt_result = await agent.get_prompt(
                "update_note",
                arguments=prompt_args,
                server_name="dayo-notes-writer",
            )

            if not prompt_result.messages:
                raise RuntimeError("MCP server returned an empty update_note prompt.")

            response = await llm.generate_str(
                message=prompt_result.messages,
            )

        await _print_usage(running_app.context.token_counter, provider)
        return response


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="note-writer",
        description="Dayo Notes Writer — AI-powered note creation and update via MCP.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default=os.environ.get("DAYO_LLM_PROVIDER", "openai"),
        help="LLM provider to use (default: openai; or set DAYO_LLM_PROVIDER env var).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- write subcommand ---
    write_parser = subparsers.add_parser(
        "write",
        help="Write a new note from raw text.",
    )
    source_group = write_parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--text",
        metavar="TEXT",
        help="Raw text to transform into a note.",
    )
    source_group.add_argument(
        "--clipboard",
        action="store_true",
        help="Read raw text from the system clipboard.",
    )
    write_parser.add_argument("--template", help="Template alias or path.")
    write_parser.add_argument("--storage", help="Storage alias or path.")
    write_parser.add_argument("--bundle", help="Config bundle name (provides defaults).")
    write_parser.add_argument("--filename", help="Output filename (optional).")

    # --- update subcommand ---
    update_parser = subparsers.add_parser(
        "update",
        help="Append content to an existing note.",
    )
    update_source = update_parser.add_mutually_exclusive_group()
    update_source.add_argument("--text", metavar="TEXT", help="Text to append.")
    update_source.add_argument(
        "--clipboard",
        action="store_true",
        help="Read text from clipboard.",
    )
    update_parser.add_argument("--file", dest="file_name", help="Target note filename.")
    update_parser.add_argument("--storage", help="Storage alias where the note lives.")
    update_parser.add_argument("--bundle", help="Config bundle name.")

    return parser


def _read_input(args) -> str:
    """Resolve raw text from --text or --clipboard."""
    if getattr(args, "clipboard", False):
        try:
            import pyperclip  # noqa: PLC0415
            text = pyperclip.paste()
            if not text:
                print("Error: Clipboard is empty.", file=sys.stderr)
                sys.exit(1)
            return text
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading clipboard: {exc}", file=sys.stderr)
            sys.exit(1)

    text = getattr(args, "text", None)
    if text:
        return text

    # Fall back to stdin if neither --text nor --clipboard provided
    if not sys.stdin.isatty():
        return sys.stdin.read()

    print(
        "Error: No input provided. Use --text '...' or --clipboard.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    """CLI entrypoint for `note-writer` command."""
    parser = _build_parser()
    args = parser.parse_args()

    provider: Provider = args.provider  # type: ignore[assignment]

    try:
        if args.command == "write":
            raw_text = _read_input(args)
            result = asyncio.run(
                run_write_note(
                    raw_text,
                    template=getattr(args, "template", None),
                    storage=getattr(args, "storage", None),
                    bundle=getattr(args, "bundle", None),
                    filename=getattr(args, "filename", None),
                    provider=provider,
                )
            )
            print(result)

        elif args.command == "update":
            append_text = _read_input(args)
            result = asyncio.run(
                run_update_note(
                    append_text,
                    file_name=getattr(args, "file_name", None),
                    storage=getattr(args, "storage", None),
                    bundle=getattr(args, "bundle", None),
                    provider=provider,
                )
            )
            print(result)

    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
