from note_writer.domain.models import NoteDraft
from note_writer.infrastructure.filesystem import PathlibFilesystem
from note_writer.application.notes import write_note
import os

def main():
    fs = PathlibFilesystem()
    draft = NoteDraft(
        title="Manual Test Note",
        body="This is a manually tested note directly on the filesystem.",
        tags=["test", "manual"],
        frontmatter={"status": "draft"}
    )
    
    # Write to a test file in the project dir
    output_path = os.path.abspath("test_manual_note.md")
    write_note(fs, output_path, draft)
    
    print(f"Wrote note to {output_path}")
    print("Content:")
    print(fs.read_text(output_path))

if __name__ == "__main__":
    main()
