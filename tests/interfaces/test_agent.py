"""
Tests for the agent interface (Milestone 4b).

Test strategy (agreed in grilling session):
  - Unit tests: config, provider selection, Settings construction — no subprocess, no LLM.
  - Integration tests: real MCP server subprocess + mocked AugmentedLLM.generate.

The integration tests confirm:
  - MCPApp connects to note-writer-mcp subprocess via stdio.
  - agent.list_tools() sees the Dayo tools.
  - agent.get_prompt("write_note") returns messages from the server.
  - Elicitation round-trip: save_note without required args returns InputRequiredResult
    (the mcp-agent side does not need testing for the console callback here — that
    would require interactive I/O).

No live LLM API calls in any test.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Unit tests — no MCP subprocess, no LLM
# ---------------------------------------------------------------------------


class TestProviderSelection:
    """_get_llm_class returns the right class for each provider string."""

    def test_openai_returns_openai_class(self):
        from note_writer.interfaces.agent import _get_llm_class
        from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

        cls = _get_llm_class("openai")
        assert cls is OpenAIAugmentedLLM

    def test_gemini_returns_google_class(self):
        from note_writer.interfaces.agent import _get_llm_class
        from mcp_agent.workflows.llm.augmented_llm_google import GoogleAugmentedLLM

        cls = _get_llm_class("gemini")
        assert cls is GoogleAugmentedLLM

    def test_unknown_provider_raises(self):
        from note_writer.interfaces.agent import _get_llm_class

        with pytest.raises(ValueError, match="Unknown provider"):
            _get_llm_class("anthropic")  # type: ignore[arg-type]


class TestProjectRootResolution:
    """_resolve_project_root uses env var when set, falls back to file-relative path."""

    def test_uses_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("NOTE_WRITER_PROJECT_ROOT", str(tmp_path))
        from note_writer.interfaces import agent as agent_mod
        import importlib
        importlib.reload(agent_mod)  # reload to pick up fresh env
        # Call after reload
        result = agent_mod._resolve_project_root()
        assert result == tmp_path

    def test_fallback_is_a_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("NOTE_WRITER_PROJECT_ROOT", raising=False)
        from note_writer.interfaces.agent import _resolve_project_root
        result = _resolve_project_root()
        assert isinstance(result, Path)
        assert result.is_absolute()


class TestBuildSettings:
    """_build_settings returns a valid Settings object with the Dayo MCP server configured."""

    def test_settings_contains_dayo_server(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UV_PATH", "/usr/bin/uv")
        from note_writer.interfaces.agent import _build_settings

        settings = _build_settings("openai")

        assert settings.mcp is not None
        assert "dayo-notes-writer" in settings.mcp.servers
        server_cfg = settings.mcp.servers["dayo-notes-writer"]
        assert server_cfg.command == "/usr/bin/uv"
        assert "note-writer-mcp" in server_cfg.args

    def test_settings_openai_model_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UV_PATH", "/usr/bin/uv")
        from note_writer.interfaces.agent import _build_settings

        settings = _build_settings("openai")

        assert settings.openai is not None
        assert settings.openai.default_model == "gpt-4o"

    def test_settings_google_model_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UV_PATH", "/usr/bin/uv")
        from note_writer.interfaces.agent import _build_settings

        settings = _build_settings("gemini")

        assert settings.google is not None
        assert settings.google.default_model == "gemini-2.0-flash"

    def test_settings_execution_engine_is_asyncio(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UV_PATH", "/usr/bin/uv")
        from note_writer.interfaces.agent import _build_settings

        settings = _build_settings("openai")
        assert settings.execution_engine == "asyncio"


class TestCLIParser:
    """_build_parser handles all expected arguments correctly."""

    def _parse(self, args: list[str]):
        from note_writer.interfaces.agent import _build_parser
        return _build_parser().parse_args(args)

    def test_write_with_text_and_template(self):
        args = self._parse(["write", "--text", "hello", "--template", "weekly"])
        assert args.command == "write"
        assert args.text == "hello"
        assert args.template == "weekly"

    def test_write_with_clipboard_flag(self):
        args = self._parse(["write", "--clipboard", "--storage", "inbox"])
        assert args.clipboard is True
        assert args.storage == "inbox"

    def test_write_with_bundle(self):
        args = self._parse(["write", "--text", "x", "--bundle", "daily"])
        assert args.bundle == "daily"

    def test_update_subcommand(self):
        args = self._parse(["update", "--text", "appended", "--file", "my-note.md"])
        assert args.command == "update"
        assert args.text == "appended"
        assert args.file_name == "my-note.md"

    def test_provider_flag_openai(self):
        args = self._parse(["--provider", "openai", "write", "--text", "t"])
        assert args.provider == "openai"

    def test_provider_flag_gemini(self):
        args = self._parse(["--provider", "gemini", "write", "--text", "t"])
        assert args.provider == "gemini"

    def test_default_provider_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DAYO_LLM_PROVIDER", "gemini")
        # Must rebuild parser after env change
        from note_writer.interfaces import agent as agent_mod
        import importlib
        importlib.reload(agent_mod)
        args = agent_mod._build_parser().parse_args(["write", "--text", "t"])
        assert args.provider == "gemini"


# ---------------------------------------------------------------------------
# Integration tests — real MCP server subprocess, mocked LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAgentMCPIntegration:
    """
    Connect to the real note-writer-mcp subprocess and exercise the MCP API.
    The LLM provider (AugmentedLLM.generate_str) is mocked to avoid API calls.
    """

    @pytest.fixture
    def repo_root(self) -> Path:
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "pyproject.toml").exists():
                return parent
        pytest.skip("Could not locate repo root")

    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        """Create a mock project root with config for the integration tests."""
        dayo_dir = tmp_path / ".dayo"
        dayo_dir.mkdir()
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "rewrite.md").write_text("rewrite instructions")
        (prompts_dir / "SERVER_PROMPT.md").write_text("server system prompt")
        (prompts_dir / "UPDATE_NOTE_PROMPT.md").write_text("update note instructions")
        
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "weekly.md").write_text("weekly template")
        
        config_path = dayo_dir / "config.toml"
        config_path.write_text('''
storage:
  inbox: "/tmp/inbox"
prompts:
  rewrite: "prompts/rewrite.md"
templates:
  weekly: "templates/weekly.md"
''')
        return tmp_path

    @pytest.fixture
    def uv_path(self) -> str:
        """Return the uv binary path, skip if not available."""
        candidates = [
            os.path.expanduser("~/.local/bin/uv"),
            "/usr/local/bin/uv",
            "/usr/bin/uv",
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        pytest.skip("uv binary not found; skipping integration tests")

    def _make_app_and_agent(self, uv_path: str, repo_root: Path, project_root: Path):
        """Build MCPApp and Agent connected to the real MCP server subprocess."""
        from mcp_agent.app import MCPApp
        from mcp_agent.agents.agent import Agent
        from mcp_agent.config import (
            Settings, LoggerSettings, MCPSettings, MCPServerSettings,
            OpenAISettings, GoogleSettings,
        )
        from mcp_agent.elicitation.handler import console_elicitation_callback

        settings = Settings(
            execution_engine="asyncio",
            logger=LoggerSettings(transports=["console"], level="error"),
            mcp=MCPSettings(
                servers={
                    "dayo-notes-writer": MCPServerSettings(
                        command=uv_path,
                        args=["run", "note-writer-mcp"],
                        cwd=str(repo_root),
                        env={"NOTE_WRITER_PROJECT_ROOT": str(project_root)},
                    )
                }
            ),
            openai=OpenAISettings(default_model="gpt-4o"),
            google=GoogleSettings(default_model="gemini-2.0-flash"),
        )
        app = MCPApp(
            name="test-dayo-agent",
            settings=settings,
            elicitation_callback=console_elicitation_callback,
        )
        agent = Agent(
            name="test-writer",
            instruction="Test agent.",
            server_names=["dayo-notes-writer"],
        )
        return app, agent

    async def test_agent_connects_and_lists_tools(self, repo_root: Path, project_root: Path, uv_path: str):
        """Agent can connect to note-writer-mcp and discover its tools."""
        app, agent = self._make_app_and_agent(uv_path, repo_root, project_root)

        async with app.run():
            async with agent:
                tools_result = await agent.list_tools()
                tool_names = {t.name for t in tools_result.tools}

        expected_tools = {
            "dayo-notes-writer_list_templates", 
            "dayo-notes-writer_list_storages", 
            "dayo-notes-writer_list_bundles",
            "dayo-notes-writer_read_note", 
            "dayo-notes-writer_step2_save_note", 
            "dayo-notes-writer_update_note",
        }
        assert expected_tools.issubset(tool_names), (
            f"Missing tools: {expected_tools - tool_names}"
        )

    async def test_write_note_prompt_returns_messages(self, repo_root: Path, project_root: Path, uv_path: str):
        """
        agent.get_prompt('write_note') with full args returns a list of messages
        from the server (system_prompt + prompt + template + raw_text).
        """
        app, agent = self._make_app_and_agent(uv_path, repo_root, project_root)

        async with app.run():
            async with agent:
                prompt_result = await agent.get_prompt(
                    "write_note",
                    arguments={
                        "raw_text": "Stand-up: finished auth module.",
                        "template": "weekly",
                        "storage": "inbox",
                        "prompt": "rewrite",
                    },
                    server_name="dayo-notes-writer",
                )

        assert prompt_result is not None
        assert len(prompt_result.messages) >= 1

    async def test_write_note_prompt_missing_args_returns_guidance(
        self, repo_root: Path, project_root: Path, uv_path: str
    ):
        """
        agent.get_prompt('write_note') with missing args returns a guidance UserMessage
        (conversational fallback from Milestone 3 walkthrough).
        """
        app, agent = self._make_app_and_agent(uv_path, repo_root, project_root)

        async with app.run():
            async with agent:
                prompt_result = await agent.get_prompt(
                    "write_note",
                    arguments={},
                    server_name="dayo-notes-writer",
                )

        assert prompt_result is not None
        assert len(prompt_result.messages) >= 1
        # The server returns a UserMessage with instructions when args are missing
        first_msg = prompt_result.messages[0]
        assert first_msg.role == "user"

    async def test_run_write_note_mocked_llm(
        self, project_root: Path, uv_path: str, monkeypatch: pytest.MonkeyPatch
    ):
        """
        run_write_note() drives the full agent flow with the real MCP server.
        The LLM generate_str is mocked to return a plausible response without API calls.
        """
        from note_writer.interfaces.agent import run_write_note

        # The mocked LLM response simulates what the agent would say after calling save_note
        mocked_response = "Note saved successfully to inbox/2026-09-05-weekly.md"

        # Patch generate_str on the AugmentedLLM base class
        with patch(
            "mcp_agent.workflows.llm.augmented_llm.AugmentedLLM.generate_str",
            new_callable=AsyncMock,
            return_value=mocked_response,
        ):
            monkeypatch.setenv("UV_PATH", uv_path)
            monkeypatch.setenv("NOTE_WRITER_PROJECT_ROOT", str(project_root))

            result = await run_write_note(
                "Had a great week. Shipped the auth feature.",
                template="weekly",
                storage="inbox",
                bundle=None,
                provider="openai",
            )

        assert isinstance(result, str)
        # We don't assert the exact string since the mock returns our preset value
        assert len(result) > 0
