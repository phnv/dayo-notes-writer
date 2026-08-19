import yaml
from note_writer.infrastructure.filesystem import Filesystem
from note_writer.domain.models import NoteDraft
from note_writer.domain.config.models import Config

def list_templates(config: Config) -> list[str]:
    """Return all configured template aliases."""
    return list(config.templates.keys())

def list_storages(config: Config) -> list[str]:
    """Return all configured storage aliases."""
    return list(config.storage.keys())

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

def update_note(fs: Filesystem, path: str, content: str) -> None:
    fs.append_text(path, content)
