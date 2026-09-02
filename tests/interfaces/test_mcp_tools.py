import pytest
import json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

import note_writer.interfaces.mcp as mcp_module
from note_writer.interfaces.mcp import build_server, AppState
from note_writer.domain.config.models import Config, BundleConfig
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem
from mcp.types import CallToolResult

FROZEN_DT = datetime(2026, 9, 2, 0, 0, 0)

@pytest.fixture
def test_config(tmp_path: Path):
    return Config(
        templates={"weekly": "templates/weekly.md"},
        prompts={"rewrite": "prompts/rewrite.md"},
        storage={"inbox": str(tmp_path / "inbox")},
        bundles={
            "my_bundle": BundleConfig(
                template="weekly",
                prompt="rewrite",
                storage="inbox",
            ),
            "daily": BundleConfig(
                template="weekly",
                prompt="rewrite",
                storage="inbox",
                filename="{date}-daily.md",
            ),
        },
        defaults={"bundle": "my_bundle"},
    )

@pytest.fixture
def mcp_server_and_state(tmp_path: Path, test_config: Config):
    prompts_dir = tmp_path / "prompts"
    templates_dir = tmp_path / "templates"
    inbox_dir = tmp_path / "inbox"
    prompts_dir.mkdir()
    templates_dir.mkdir()
    inbox_dir.mkdir()

    (templates_dir / "weekly.md").write_text("# Weekly Template", encoding="utf-8")
    (prompts_dir / "rewrite.md").write_text("Rewrite this", encoding="utf-8")

    fs = PathlibFilesystem()
    resolver = PathResolver(app_root=tmp_path)

    server = build_server(test_config, fs, resolver, prompts_dir, templates_dir)

    state = AppState(
        config=test_config,
        fs=fs,
        resolver=resolver,
        prompts_dir=prompts_dir,
        templates_dir=templates_dir,
    )
    mcp_module._state = state

    yield server, state

    mcp_module._state = None


# Mocking Context for Tool calls
class MockRequestContext:
    def __init__(self, state):
        self.lifespan_context = {"state": state}
        self.protocol_version = "2026-07-28"

class MockContext:
    def __init__(self, state):
        self.request_context = MockRequestContext(state)


@pytest.mark.asyncio
async def test_list_templates(mcp_server_and_state):
    server, state = mcp_server_and_state
    result = await server.call_tool("list_templates", {}, context=MockContext(state))
    assert isinstance(result, CallToolResult)
    assert "weekly" in result.content[0].text


@pytest.mark.asyncio
async def test_write_and_read_note(mcp_server_and_state, tmp_path):
    server, state = mcp_server_and_state

    # Write — uses renamed 'storage' arg
    write_args = {
        "storage": "inbox",
        "filename": "test.md",
        "title": "Test Title",
        "body": "Test Body",
        "tags": ["test"],
        "frontmatter": json.dumps({"test": "data"})
    }
    result = await server.call_tool("step2_save_note", write_args, context=MockContext(state))
    assert "Successfully wrote note" in result.content[0].text

    inbox_dir = tmp_path / "inbox"
    assert (inbox_dir / "test.md").exists()
    content = (inbox_dir / "test.md").read_text(encoding="utf-8")
    assert "Test Body" in content
    assert "test: data" in content

    # Read — uses renamed 'storage' arg
    read_args = {"storage": "inbox", "filename": "test.md"}
    read_result = await server.call_tool("read_note", read_args, context=MockContext(state))
    assert "Test Body" in read_result.content[0].text


@pytest.mark.asyncio
async def test_resources(mcp_server_and_state):
    server, state = mcp_server_and_state

    template_res = await server.read_resource("templates://weekly")
    assert "Weekly Template" in template_res[0].content

    prompt_res = await server.read_resource("prompts://rewrite")
    assert "Rewrite this" in prompt_res[0].content

    config_res = await server.read_resource("config://templates")
    assert "weekly" in config_res[0].content


@pytest.mark.asyncio
async def test_read_note_with_bundle_only(mcp_server_and_state, tmp_path):
    """read_note should resolve storage from bundle without requiring an explicit storage arg."""
    server, state = mcp_server_and_state

    inbox_dir = tmp_path / "inbox"
    (inbox_dir / "bundle_test.md").write_text("# Bundle Test\nHello from bundle.", encoding="utf-8")

    result = await server.call_tool(
        "read_note",
        {"bundle": "my_bundle", "filename": "bundle_test.md"},
        context=MockContext(state),
    )
    assert isinstance(result, CallToolResult)
    assert "Hello from bundle" in result.content[0].text


@pytest.mark.asyncio
async def test_read_note_explicit_storage_overrides_bundle(mcp_server_and_state, tmp_path):
    """An explicit storage should win over the bundle storage."""
    server, state = mcp_server_and_state

    inbox_dir = tmp_path / "inbox"
    (inbox_dir / "override_test.md").write_text("# Override Test", encoding="utf-8")

    result = await server.call_tool(
        "read_note",
        {"bundle": "my_bundle", "storage": "inbox", "filename": "override_test.md"},
        context=MockContext(state),
    )
    assert isinstance(result, CallToolResult)
    assert "Override Test" in result.content[0].text


@pytest.mark.asyncio
async def test_read_note_defaults_bundle_fallback(mcp_server_and_state, tmp_path):
    """When neither bundle nor storage is supplied, defaults.bundle should fill storage."""
    server, state = mcp_server_and_state

    inbox_dir = tmp_path / "inbox"
    (inbox_dir / "defaults_test.md").write_text("# Defaults Test", encoding="utf-8")

    result = await server.call_tool(
        "read_note",
        {"filename": "defaults_test.md"},
        context=MockContext(state),
    )
    assert isinstance(result, CallToolResult)
    assert "Defaults Test" in result.content[0].text


# --- Slice D: bundle filename integration tests ---

@pytest.mark.asyncio
async def test_save_note_uses_bundle_filename(mcp_server_and_state, tmp_path):
    """step2_save_note with a bundle that has filename — no explicit filename needed."""
    server, state = mcp_server_and_state

    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT

        result = await server.call_tool(
            "step2_save_note",
            {
                "bundle": "daily",
                "title": "My Daily Note",
                "body": "Body text",
                "tags": [],
                "frontmatter": "{}",
            },
            context=MockContext(state),
        )

    assert isinstance(result, CallToolResult)
    assert not result.is_error
    inbox_dir = tmp_path / "inbox"
    assert (inbox_dir / "2026-09-02-daily.md").exists()


@pytest.mark.asyncio
async def test_save_note_explicit_filename_overrides_bundle(mcp_server_and_state, tmp_path):
    """Explicit filename arg wins over bundle filename."""
    server, state = mcp_server_and_state

    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT

        result = await server.call_tool(
            "step2_save_note",
            {
                "bundle": "daily",
                "filename": "my-override.md",
                "title": "Override",
                "body": "Body",
                "tags": [],
                "frontmatter": "{}",
            },
            context=MockContext(state),
        )

    inbox_dir = tmp_path / "inbox"
    assert (inbox_dir / "my-override.md").exists()
    assert not (inbox_dir / "2026-09-02-daily.md").exists()


@pytest.mark.asyncio
async def test_update_note_uses_bundle_filename(mcp_server_and_state, tmp_path):
    """update_note with bundle filename — resolves and appends to correct file."""
    server, state = mcp_server_and_state

    inbox_dir = tmp_path / "inbox"
    (inbox_dir / "2026-09-02-daily.md").write_text("# Existing", encoding="utf-8")

    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT

        result = await server.call_tool(
            "update_note",
            {
                "bundle": "daily",
                "content": "\nAppended content",
            },
            context=MockContext(state),
        )

    assert isinstance(result, CallToolResult)
    assert not result.is_error
    updated = (inbox_dir / "2026-09-02-daily.md").read_text(encoding="utf-8")
    assert "Appended content" in updated
