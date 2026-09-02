"""Domain helpers for parsing Markdown with YAML frontmatter."""


def has_frontmatter(content: str) -> bool:
    """Return True if content begins with a YAML frontmatter block (--- ... ---)."""
    if not content.startswith("---\n"):
        return False
    # Find the closing --- after the opening one
    closing = content.find("\n---\n", 4)
    return closing != -1


def split_frontmatter(content: str) -> tuple[str, str]:
    """Split content into (header, body).

    header — the raw '---\\n...\\n---\\n' block, or '' if none is present.
    body   — everything after the header (may be empty string).
    """
    if not has_frontmatter(content):
        return "", content

    closing_start = content.find("\n---\n", 4)
    # closing_start points to the '\n' before '---\n'; include through that '---\n'
    split_pos = closing_start + len("\n---\n")
    header = content[:split_pos]
    body = content[split_pos:]
    return header, body
