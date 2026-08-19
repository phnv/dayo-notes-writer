def test_note_draft_validates_required_fields():
    from note_writer.domain.models import NoteDraft

    draft = NoteDraft(
        title="My Note",
        body="Note content",
        tags=["idea", "draft"],
        frontmatter={"custom": 123}
    )

    assert draft.title == "My Note"
    assert draft.body == "Note content"
    assert draft.tags == ["idea", "draft"]
    assert draft.frontmatter == {"custom": 123}
