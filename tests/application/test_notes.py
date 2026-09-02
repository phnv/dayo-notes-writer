import pytest
from note_writer.application.notes import write_note, read_note, update_note
from note_writer.domain.models import NoteDraft

class FakeFilesystem:
    def __init__(self):
        self.files = {}
        
    def write_text(self, path: str, content: str) -> None:
        self.files[path] = content
        
    def read_text(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]
        
    def append_text(self, path: str, content: str) -> None:
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        self.files[path] += content

def test_write_note():
    fs = FakeFilesystem()
    draft = NoteDraft(
        title="My Note",
        body="This is my body.",
        tags=["idea"],
        frontmatter={"custom": "value"}
    )
    
    write_note(fs, "/path/to/my_note.md", draft)
    
    content = fs.read_text("/path/to/my_note.md")
    assert "# My Note" in content
    assert "custom: value" in content
    assert "This is my body." in content

def test_read_note():
    fs = FakeFilesystem()
    fs.write_text("/path/to/read.md", "Stored content")
    
    content = read_note(fs, "/path/to/read.md")
    assert content == "Stored content"

def test_update_note():
    fs = FakeFilesystem()
    fs.write_text("/path/to/update.md", "Original.")

    update_note(fs, "/path/to/update.md", "\nAppended.")

    content = fs.read_text("/path/to/update.md")
    assert content == "Original.\nAppended."


def test_update_note_bottom_is_default():
    fs = FakeFilesystem()
    fs.write_text("/path/to/update.md", "Original.")

    update_note(fs, "/path/to/update.md", "\nAppended.", append_mode="bottom")

    content = fs.read_text("/path/to/update.md")
    assert content == "Original.\nAppended."


def test_update_note_top_no_frontmatter():
    fs = FakeFilesystem()
    fs.write_text("/path/to/update.md", "Existing body.")

    update_note(fs, "/path/to/update.md", "Prepended content.", append_mode="top")

    content = fs.read_text("/path/to/update.md")
    assert content == "Prepended content.\n\nExisting body."


def test_update_note_top_with_frontmatter():
    fs = FakeFilesystem()
    existing = "---\ntitle: My Note\n---\n\nExisting body."
    fs.write_text("/path/to/update.md", existing)

    update_note(fs, "/path/to/update.md", "Prepended content.", append_mode="top")

    content = fs.read_text("/path/to/update.md")
    assert content == "---\ntitle: My Note\n---\n\nPrepended content.\n\nExisting body."


def test_update_note_top_with_frontmatter_empty_body():
    fs = FakeFilesystem()
    existing = "---\ntitle: Only Header\n---\n"
    fs.write_text("/path/to/update.md", existing)

    update_note(fs, "/path/to/update.md", "New content.", append_mode="top")

    content = fs.read_text("/path/to/update.md")
    assert content == "---\ntitle: Only Header\n---\n\nNew content."


def test_update_note_invalid_mode_raises():
    fs = FakeFilesystem()
    fs.write_text("/path/to/update.md", "Some content.")

    import pytest
    with pytest.raises(ValueError, match="append_mode must be 'top' or 'bottom'"):
        update_note(fs, "/path/to/update.md", "content", append_mode="middle")
