import os
import json
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer, Context
from mcp.server.mcpserver.prompts import base
from mcp.types import (
    ToolAnnotations,
    InputRequiredResult,
    ElicitRequest,
    ElicitRequestFormParams,
    TextResourceContents,
    EmbeddedResource,
)

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
    list_bundles as app_list_bundles,
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

    # @FINAL-REVIEW: TEMPLATES CAN BE LOCAL TO PROJECT OR ANY OTHER FOLDER
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
        description="List all available configuration bundles."
    )
    def list_bundles(ctx: Context) -> list[str]:
        state: AppState = ctx.request_context.lifespan_context["state"]
        return app_list_bundles(state.config)

    @mcp.tool(
        annotations=ToolAnnotations(read_only_hint=True),
        description="Read a note's content from a specific storage alias and filename."
    )
    def read_note(storage_alias: str = None, filename: str = None, ctx: Context = None) -> str | InputRequiredResult:
        if not storage_alias or not filename:
            if ctx and ctx.request_context.protocol_version < "2026-07-28":
                raise ValueError("Missing required arguments: storage_alias and filename are required.")
            return InputRequiredResult(
                inputRequests={
                    "missing_args": ElicitRequest(
                        params=ElicitRequestFormParams(
                            mode="form",
                            message="Please provide both storage_alias and filename.",
                            requestedSchema={
                                "type": "object",
                                "properties": {
                                    "storage_alias": {"type": "string"},
                                    "filename": {"type": "string"}
                                },
                                "required": ["storage_alias", "filename"]
                            }
                        )
                    )
                }
            )

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
    def save_note(
        title: str, 
        body: str, 
        tags: list[str], 
        frontmatter: str, # passed as JSON string
        storage_alias: str = None, 
        filename: str = None, 
        ctx: Context = None
    ) -> str | InputRequiredResult:
        if not storage_alias or not filename:
            if ctx and ctx.request_context.protocol_version < "2026-07-28":
                raise ValueError("Missing required arguments: storage_alias and filename are required.")
            return InputRequiredResult(
                inputRequests={
                    "missing_args": ElicitRequest(
                        params=ElicitRequestFormParams(
                            mode="form",
                            message="Please provide both storage_alias and filename.",
                            requestedSchema={
                                "type": "object",
                                "properties": {
                                    "storage_alias": {"type": "string"},
                                    "filename": {"type": "string"}
                                },
                                "required": ["storage_alias", "filename"]
                            }
                        )
                    )
                }
            )

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
    def update_note(content: str, storage_alias: str = None, filename: str = None, ctx: Context = None) -> str | InputRequiredResult:
        if not storage_alias or not filename:
            if ctx and ctx.request_context.protocol_version < "2026-07-28":
                raise ValueError("Missing required arguments: storage_alias and filename are required.")
            return InputRequiredResult(
                inputRequests={
                    "missing_args": ElicitRequest(
                        params=ElicitRequestFormParams(
                            mode="form",
                            message="Please provide both storage_alias and filename.",
                            requestedSchema={
                                "type": "object",
                                "properties": {
                                    "storage_alias": {"type": "string"},
                                    "filename": {"type": "string"}
                                },
                                "required": ["storage_alias", "filename"]
                            }
                        )
                    )
                }
            )

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

    @mcp.resource("config://bundles")
    def get_bundles_config() -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
        return json.dumps(_state.config.bundles, indent=2)

    @mcp.resource("config://system_prompt")
    def get_system_prompt() -> str:
        if not _state:
            raise RuntimeError("Server state not initialized")
        prompt_path = _state.prompts_dir / "SERVER_PROMPT.md"
        try:
            return _state.fs.read_text(str(prompt_path))
        except FileNotFoundError:
            raise ValueError(f"System prompt file not found at {prompt_path}")

    # --- Prompts (MCP Prompts) ---
    @mcp.prompt()
    def write_note(raw_text: str, template: str = None, prompt: str = None, storage: str = None, ctx: Context = None) -> list[base.Message] | InputRequiredResult:
        """Prompt to write a new note using a specific template and instruction prompt."""
        if not _state:
            raise RuntimeError("Server state not initialized")
            
        if not template or not prompt or not storage:
            if ctx and ctx.request_context.protocol_version < "2026-07-28":
                return [base.UserMessage(content="You are missing required arguments for this prompt (template, prompt, and storage). Please ask the user to provide these details and then try again.")]
            return InputRequiredResult(
                inputRequests={
                    "missing_args": ElicitRequest(
                        params=ElicitRequestFormParams(
                            mode="form",
                            message="Please provide template, prompt, and storage.",
                            requestedSchema={
                                "type": "object",
                                "properties": {
                                    "template": {"type": "string"},
                                    "prompt": {"type": "string"},
                                    "storage": {"type": "string"}
                                },
                                "required": ["template", "prompt", "storage"]
                            }
                        )
                    )
                }
            )
            
        return [
            base.UserMessage(
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri="config://system_prompt",
                        mimeType="text/markdown",
                        text=get_system_prompt()
                    )
                )
            ),
            base.UserMessage(
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri=f"prompts://{prompt}",
                        mimeType="text/markdown",
                        text=get_prompt_file(prompt)
                    )
                )
            ),
            base.UserMessage(
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri=f"templates://{template}",
                        mimeType="text/markdown",
                        text=get_template(template)
                    )
                )
            ),
            base.UserMessage(
                content=f"Raw Text:\n{raw_text}\n\nTarget Storage Alias: {storage}"
            )
        ]

    @mcp.prompt()
    def update_note(raw_text: str, file_name: str = None, storage: str = None, ctx: Context = None) -> list[base.Message] | InputRequiredResult:
        """Prompt to append content to an existing note."""
        if not _state:
            raise RuntimeError("Server state not initialized")

        if not file_name or not storage:
            if ctx and ctx.request_context.protocol_version < "2026-07-28":
                return [base.UserMessage(content="You are missing required arguments to update this note (file_name and storage). Please ask the user to provide these details and then try again.")]
            return InputRequiredResult(
                inputRequests={
                    "missing_args": ElicitRequest(
                        params=ElicitRequestFormParams(
                            mode="form",
                            message="Please provide both file_name and storage to update.",
                            requestedSchema={
                                "type": "object",
                                "properties": {
                                    "file_name": {"type": "string"},
                                    "storage": {"type": "string"}
                                },
                                "required": ["file_name", "storage"]
                            }
                        )
                    )
                }
            )

        update_prompt_path = _state.prompts_dir / "UPDATE_NOTE_PROMPT.md"
        try:
            update_prompt_text = _state.fs.read_text(str(update_prompt_path))
        except FileNotFoundError:
            update_prompt_text = "<Error: UPDATE_NOTE_PROMPT.md not found>"

        return [
            base.UserMessage(
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri="config://system_prompt",
                        mimeType="text/markdown",
                        text=get_system_prompt()
                    )
                )
            ),
            base.UserMessage(
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri="prompts://UPDATE_NOTE_PROMPT.md",
                        mimeType="text/markdown",
                        text=update_prompt_text
                    )
                )
            ),
            base.UserMessage(
                content=f"Raw Text:\n{raw_text}\n\nTarget File: {file_name}\nTarget Storage Alias: {storage}"
            )
        ]

    return mcp


# Setup default module-level MCP server instance for main.py entrypoint
def run_server() -> MCPServer:
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


mcp = run_server()
