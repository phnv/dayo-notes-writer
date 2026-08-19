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
