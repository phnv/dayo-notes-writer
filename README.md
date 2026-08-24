# Dayo Notes Writer (In Progress)

Dayo Notes Writer is a local, ephemeral note transformation utility powered by the Model Context Protocol (MCP). It acts as an intelligent bridge between raw text and your structured note vault. Instead of relying on rigid scripts, it leverages language models to dynamically shape your text into properly formatted notes using your personal templates.

> [!NOTE]
> **Protocol Compatibility:** This project supports the most recent MCP protocol version (28/07/2026) while strictly maintaining backward compatibility with older versions.

## Features & Capabilities

- **Template-Driven Output:** Automatically formats raw text into structured notes, such as meetings, daily logs, or weekly reviews.
- **Intelligent Storage Routing:** Saves your notes directly to predefined directories in your vault based on simple storage aliases.
- **MCP Native:** Exposes its capabilities as standard MCP tools and resources, allowing seamless integration with any MCP-compatible agent or client.
- **Strict Separation of Concerns:** The language model focuses purely on text generation and content formatting, while the local application retains full control over file paths, naming conventions, and directory structures.

## Getting Started

This project is built for a Linux/WSL environment and relies on modern Python tooling.

**Prerequisites:**
- A working WSL (Ubuntu) environment.
- The `uv` package manager installed in your WSL environment.
- An MCP-compatible client or agent (the lightweight client is currently in development).

## Installation & VS Code Setup

To use Dayo Notes Writer within Visual Studio Code (via an MCP-compatible extension like Cline, Roo Code, or Claude Dev), you need to configure your extension to launch the server.

Because the project runs in WSL, your VS Code MCP configuration must bridge the Windows-to-Linux gap. In your extension's MCP settings file, define a new server that invokes the WSL executable. Configure the arguments to target your Ubuntu distribution, change to the project directory, and use the `uv` tool to run the MCP server module. This allows your VS Code agent to securely interact with your Linux-based note vault.

For reference, here is how the `mcp.json` settings file looks like with the server setup:

```json
{
  "mcpServers": {
    "dayo-notes-writer": {
      "command": "wsl.exe",
      "args": [
        "-d",
        "Ubuntu",
        "--cd",
        "/home/<root>/<your-project-folder>/dayo-notes-writer",
        "--",
        "/home/<root>/.local/bin/uv",
        "run",
        "note-writer-mcp"
      ]
    }
  }
}
```

## Configuration

Configuration is managed via simple YAML files, keeping the setup declarative and easy to version control.

- **Templates:** You define templates to dictate the structure of your notes. Each template alias binds a markdown layout, an instruction prompt for the LLM, and a default storage location.
- **Storages:** You define storage aliases that point to absolute paths on your filesystem (like specific folders in your Obsidian vault). The application strictly resolves these aliases, ensuring notes are only saved in authorized locations.

> [!TIP]
> The configuration system uses a resolution priority, allowing you to set global defaults that can be overridden by specific template settings or command-line arguments.

## Available MCP Tools & Resources

The server exposes a set of deterministic capabilities to your agent:

**Tools:**
- `save_note`: Writes a completely new note based on your input and selected template.
- `update_note`: Appends to or modifies an existing note.
- `read_note`: Retrieves the contents of a specific note by path or alias.
- `list_templates`: Shows all available note templates you have configured.
- `list_storages`: Displays all configured storage directories.
- `list_bundles`: Lists available configuration bundles for quick execution.

**Resources:**
- The server provides direct resource access to your configured templates, prompts, and global settings, allowing agents to read the context before taking action.

> [!IMPORTANT]
> The MCP server handles all interactions ephemerally. It starts up on demand when your agent connects and shuts down cleanly when the session ends, leaving no background daemons running.

## Roadmap

The following enhancements are planned for upcoming releases:

- Bundle, storage, template, and prompt creation commands for faster scaffolding.
- A dedicated, lightweight agent to host the MCP client natively.
- Quick desktop activation icons for seamless local access outside of traditional IDEs.
