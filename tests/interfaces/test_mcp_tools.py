import pytest
import json
from pathlib import Path

import note_writer.interfaces.mcp as mcp_module
from note_writer.interfaces.mcp import build_server, AppState
from note_writer.domain.config.models import Config, BundleConfig
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem
from mcp.types import CallToolResult

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
            )
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
    
    # Initialize the global state explicitly for tests
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
    
    # We call the registered tool function directly or via call_tool
    # Since call_tool is async, we can await it. We must pass a Context if the tool expects it.
    # Actually, MCPServer's call_tool might not need us to pass context manually if it doesn't inject it from lifespan in test without a real request.
    # Wait, call_tool takes a context argument:
    # call_tool(self, name: str, arguments: dict, context: Context | None = None)
    
    result = await server.call_tool("list_templates", {}, context=MockContext(state))
    # mcp sdk might return the literal list if we use it, but `call_tool` returns a `CallToolResult`
    assert isinstance(result, CallToolResult)
    # The return value from tool is json-serialized into TextContent
    # Let's just check the string representation
    assert "weekly" in result.content[0].text


@pytest.mark.asyncio
async def test_write_and_read_note(mcp_server_and_state, tmp_path):
    server, state = mcp_server_and_state
    
    # Write
    write_args = {
        "storage_alias": "inbox",
        "filename": "test.md",
        "title": "Test Title",
        "body": "Test Body",
        "tags": ["test"],
        "frontmatter": json.dumps({"test": "data"})
    }
    result = await server.call_tool("step2_save_note", write_args, context=MockContext(state))
    assert "Successfully wrote note" in result.content[0].text
    
    # Verify on disk
    inbox_dir = tmp_path / "inbox"
    assert (inbox_dir / "test.md").exists()
    content = (inbox_dir / "test.md").read_text(encoding="utf-8")
    assert "Test Body" in content
    assert "test: data" in content
    
    # Read
    read_args = {
        "storage_alias": "inbox",
        "filename": "test.md"
    }
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
    """read_note should resolve storage_alias from bundle without requiring an explicit storage_alias arg."""
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
    """An explicit storage_alias should win over the bundle's storage."""
    server, state = mcp_server_and_state

    inbox_dir = tmp_path / "inbox"
    (inbox_dir / "override_test.md").write_text("# Override Test", encoding="utf-8")

    result = await server.call_tool(
        "read_note",
        {"bundle": "my_bundle", "storage_alias": "inbox", "filename": "override_test.md"},
        context=MockContext(state),
    )
    assert isinstance(result, CallToolResult)
    assert "Override Test" in result.content[0].text


@pytest.mark.asyncio
async def test_read_note_defaults_bundle_fallback(mcp_server_and_state, tmp_path):
    """When neither bundle nor storage_alias is supplied, defaults.bundle should fill storage."""
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
