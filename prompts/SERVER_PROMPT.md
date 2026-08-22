# About This Server

This MCP server provides tools and predefined instructions for transforming and storing Markdown notes. Its primary workflows are **writing new notes** and **updating existing notes**. Agents should follow the workflow instructions exposed by the server rather than independently inventing storage or transformation behavior. Note transformations are **lossless structural transformations**: preserve the source information, meaning, language, dates, status, priorities and uncertainty while improving structure and consistency. For existing notes, always read the note before updating it and use the existing content as the authority for its style and structure. File operations must use the required `file_name` and `storage` parameters and should be performed through the server's exposed tools.

## Mandatory Workflows

### Creating a New Note (2 steps — both required)

1. **Step 1 — Call the `write_note` prompt** (MCP Prompt, not a tool): provide `raw_text`, `template`, `prompt`, and `storage`. This returns the system instructions, the selected template, and the transformation rules. Use these to generate the transformed note content.
2. **Step 2 — Call `step2_save_note`** (MCP Tool): provide the LLM-generated `title`, `body`, `tags`, `frontmatter` (as a JSON string), `storage_alias`, and `filename`. Do not call this tool without first completing Step 1.

> Skipping Step 1 bypasses the template and transformation rules. The resulting note will not conform to the server's format.

### Updating an Existing Note (2 steps — both required)

1. **Step 1 — Call the `update_note` prompt** (MCP Prompt): provide `raw_text`, `file_name`, and `storage`. This returns the system instructions and loads the existing note as context.
2. **Step 2 — Call `update_note`** (MCP Tool): append only the rewritten content using the same `file_name` and `storage_alias`.
