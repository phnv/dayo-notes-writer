import pytest
from note_writer.domain.markdown import has_frontmatter, split_frontmatter


class TestHasFrontmatter:
    def test_detects_yaml_frontmatter(self):
        content = "---\ntitle: My Note\n---\n\nBody text."
        assert has_frontmatter(content) is True

    def test_returns_false_when_no_frontmatter(self):
        content = "# Just a heading\n\nSome body."
        assert has_frontmatter(content) is False

    def test_returns_false_for_empty_string(self):
        assert has_frontmatter("") is False

    def test_requires_opening_triple_dash_at_start(self):
        content = "Some text\n---\ntitle: value\n---\n"
        assert has_frontmatter(content) is False

    def test_returns_false_when_no_closing_dashes(self):
        content = "---\ntitle: My Note\n"
        assert has_frontmatter(content) is False


class TestSplitFrontmatter:
    def test_splits_header_and_body(self):
        content = "---\ntitle: My Note\n---\n\nBody text."
        header, body = split_frontmatter(content)
        assert header == "---\ntitle: My Note\n---\n"
        assert body == "\nBody text."

    def test_returns_empty_header_when_no_frontmatter(self):
        content = "# Just a heading\n\nSome body."
        header, body = split_frontmatter(content)
        assert header == ""
        assert body == content

    def test_empty_body_after_frontmatter(self):
        content = "---\ntitle: Note\n---\n"
        header, body = split_frontmatter(content)
        assert header == "---\ntitle: Note\n---\n"
        assert body == ""

    def test_multiline_frontmatter(self):
        content = "---\ntitle: My Note\ntags:\n  - idea\n  - work\n---\n\nBody here."
        header, body = split_frontmatter(content)
        assert header == "---\ntitle: My Note\ntags:\n  - idea\n  - work\n---\n"
        assert body == "\nBody here."
