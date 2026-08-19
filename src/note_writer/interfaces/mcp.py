import os
import json
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer, Context
from mcp.types import ToolAnnotations

from note_writer.domain.config.models import Config
from note_writer.domain.config.loader import load_config_from_file
from note_writer.domain.config.resolver import PathResolver
from note_writer.domain.models import NoteDraft
from note_writer.domain.errors import NoteWriterError
from note_writer.application.notes import (
    read_note as app_read_note,
    write_note as app_write_note,
    update_note as app_update_note,
    list_templates as app_list_templates,
    list_storages as app_list_storages,
)
from note_writer.infrastructure.filesystem import PathlibFilesystem


@dataclass
class AppState:
    config: Config
    fs: PathlibFilesystem
    resolver: PathResolver
    prompts_dir: Path
    templates_dir: Path


# Global state for static resources that can't receive Context
_state: AppState | None = None


def get_default_paths():
    """Resolve default paths relative to the project root."""
    # Assuming this runs from project root or via uv
    root = Path.cwd()
    config_path = Path(os.environ.get("CONFIG_PATH", root / "config" / "config.yaml"))
    prompts_dir = Path(os.environ.get("PROMPTS_DIR", root / "prompts"))
    templates_dir = Path(os.environ.get("TEMPLATES_DIR", root / "templates"))
    return config_path, prompts_dir, templates_dir


def build_server(config: Config, fs: PathlibFilesystem, resolver: PathResolver, prompts_dir: Path, templates_dir: Path) -> MCPServer:
    """Factory to build the MCP server, useful for isolated testing."""

    @asynccontextmanager
    async def lifespan(server: MCPServer):
        global _state
        _state = AppState(
            config=config,
            fs=fs,
            resolver=resolver,
            prompts_dir=prompts_dir,
            templates_dir=templates_dir,
        )
        yield {"state": _state}
        _state = None

    mcp = MCPServer("dayo-notes-writer", version="0.1.0", lifespan=lifespan)

    # --- Tools ---

    @mcp.tool(
        annotations=ToolAnnotations(read_only_hint=True),
        description="List all available note templates."
    )
    def list_templates(ctx: Context) -> list[str]:
        state: AppState = ctx.request_context.lifespan_context["state"]
        return app_list_templates(state.config)

    @mcp.tool(
        annotations=ToolAnnotations(read_only_hint=True),
        description="List all available storage aliases."
    )
    def list_storages(ctx: Context) -> list[str]:
        state: AppState = ctx.request_context.lifespan_context["state"]
        return app_list_storages(state.config)

    @mcp.tool(
        annotations=ToolAnnotations(read_only_hint=True),
        description="Read a note's content from a specific storage alias and filename."
    )
    def read_note(storage_alias: str, filename: str, ctx: Context) -> str:
        state: AppState = ctx.request_context.lifespan_context["state"]
        
        if storage_alias not in state.config.storage:
            raise ValueError(f"Storage alias '{storage_alias}' not found in configuration.")
            
        try:
            base_path = state.resolver.resolve(state.config.storage[storage_alias])
            file_path = base_path / filename
            return app_read_note(state.fs, str(file_path))
        except NoteWriterError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Failed to read note: {e}")

    @mcp.tool(
        annotations=ToolAnnotations(destructive_hint=True),
        description="Write a new note to a specific storage alias. Overwrites if it exists."
    )
    def write_note(
        storage_alias: str, 
        filename: str, 
        title: str, 
        body: str, 
        tags: list[str], 
        frontmatter: str, # passed as JSON string
        ctx: Context
    ) -> str:
        state: AppState = ctx.request_context.lifespan_context["state"]
        
        if storage_alias not in state.config.storage:
            raise ValueError(f"Storage alias '{storage_alias}' not found in configuration.")
            
        try:
            frontmatter_dict = json.loads(frontmatter) if frontmatter else {}
        except json.JSONDecodeError:
            raise ValueError("frontmatter must be a valid JSON string.")
            
        draft = NoteDraft(
            title=title,
            body=body,
            tags=tags,
            frontmatter=frontmatter_dict
        )
        
        try:
            base_path = state.resolver.resolve(state.config.storage[storage_alias])
            file_path = base_path / filename
            app_write_note(state.fs, str(file_path), draft)
            return f"Successfully wrote note to {file_path}"
        except NoteWriterError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Failed to write note: {e}")

    @mcp.tool(
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False),
        description="Append content to an existing note."
    )
    def update_note(storage_alias: str, filename: str, content: str, ctx: Context) -> str:
        state: AppState = ctx.request_context.lifespan_context["state"]
        
        if storage_alias not in state.config.storage:
            raise ValueError(f"Storage alias '{storage_alias}' not found in configuration.")
            
        try:
            base_path = state.resolver.resolve(state.config.storage[storage_alias])
            file_path = base_path / filename
            app_update_note(state.fs, str(file_path), content)
            return f"Successfully updated note at {file_path}"
        except NoteWriterError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Failed to update note: {e}")

    # --- Resources ---

    @mcp.resource("templates://{name}")
    def get_template(name: str) -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
            
        if name not in _state.config.templates:
            raise ValueError(f"Template alias '{name}' not found.")
            
        template_rel_path = _state.config.templates[name]
        # Resolve relative to templates_dir or just read if it's already a path
        template_path = _state.templates_dir.parent / template_rel_path
        
        try:
            return _state.fs.read_text(str(template_path))
        except FileNotFoundError:
            raise ValueError(f"Template file not found at {template_path}")

    @mcp.resource("prompts://{name}")
    def get_prompt_file(name: str) -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
            
        if name not in _state.config.prompts:
            raise ValueError(f"Prompt alias '{name}' not found.")
            
        prompt_rel_path = _state.config.prompts[name]
        prompt_path = _state.prompts_dir.parent / prompt_rel_path
        
        try:
            return _state.fs.read_text(str(prompt_path))
        except FileNotFoundError:
            raise ValueError(f"Prompt file not found at {prompt_path}")

    @mcp.resource("config://templates")
    def get_templates_config() -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
        return json.dumps(_state.config.templates, indent=2)

    @mcp.resource("config://storages")
    def get_storages_config() -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
        return json.dumps(_state.config.storage, indent=2)

    # --- Prompts (MCP Prompts) ---

    @mcp.prompt()
    def rewrite_note(raw_text: str, template: str, storage: str) -> list[dict]:
        """Prompt to rewrite a note using a specific template."""
        if not _state:
            raise RuntimeError("Server state not initialized")
            
        # Get the actual template content to include in the prompt
        try:
            template_content = get_template(template)
        except Exception as e:
            template_content = f"<Error loading template: {e}>"

        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please rewrite the following raw text into a note.\n\n"
                        f"Raw Text:\n{raw_text}\n\n"
                        f"Template to follow:\n{template_content}\n\n"
                        f"Target Storage Alias: {storage}\n"
                    )
                }
            }
        ]

    return mcp


# Setup default module-level MCP server instance for main.py entrypoint
def create_default_server() -> MCPServer:
    config_path, prompts_dir, templates_dir = get_default_paths()
    try:
        config = load_config_from_file(config_path)
    except NoteWriterError as e:
        # Fallback to empty config if not running in a configured project yet
        # Better to have the server start and return errors on use than crash on boot
        # if the user hasn't created the config file yet.
        print(f"Warning: Could not load config: {e}")
        config = Config()
        
    fs = PathlibFilesystem()
    resolver = PathResolver(app_root=Path.cwd())
    return build_server(config, fs, resolver, prompts_dir, templates_dir)


mcp = create_default_server()
