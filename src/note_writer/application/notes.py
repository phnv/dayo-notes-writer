import yaml
from note_writer.infrastructure.filesystem import Filesystem
from note_writer.domain.models import NoteDraft
from note_writer.domain.config.models import Config
from note_writer.domain.markdown import has_frontmatter, split_frontmatter

def list_templates(config: Config) -> list[str]:
    """Return all configured template aliases."""
    return list(config.templates.keys())

def list_storages(config: Config) -> list[str]:
    """Return all configured storage aliases."""
    return list(config.storage.keys())

def list_bundles(config: Config) -> list[str]:
    """Return all configured bundle aliases."""
    return list(config.bundles.keys())

def write_note(fs: Filesystem, path: str, draft: NoteDraft) -> None:
    # Build markdown with frontmatter
    lines = []
    if draft.frontmatter:
        lines.append("---")
        lines.append(yaml.dump(draft.frontmatter, default_flow_style=False).strip())
        lines.append("---")
    
    if draft.title:
        lines.append(f"# {draft.title}")
        lines.append("")
        
    lines.append(draft.body)
    
    if draft.tags:
        lines.append("")
        tags_line = " ".join(f"#{t}" for t in draft.tags)
        lines.append(tags_line)
        
    content = "\n".join(lines)
    fs.write_text(path, content)

def read_note(fs: Filesystem, path: str) -> str:
    return fs.read_text(path)

def update_note(fs: Filesystem, path: str, content: str, append_mode: str = "bottom") -> None:
    if append_mode not in ("top", "bottom"):
        raise ValueError("append_mode must be 'top' or 'bottom'")

    if append_mode == "bottom":
        fs.append_text(path, content)
        return

    # append_mode == "top": insert below any YAML frontmatter
    existing = fs.read_text(path)
    header, body = split_frontmatter(existing)

    parts = []
    if header:
        parts.append(header.rstrip("\n"))
    parts.append(content)
    if body:
        parts.append(body.lstrip("\n"))

    new_content = "\n\n".join(parts)
    fs.write_text(path, new_content)

