"""Slice A — TDD tests for expand_filename_tokens (RED before implementation)."""
import re
import pytest
from unittest.mock import patch
from datetime import datetime

from note_writer.interfaces.mcp import expand_filename_tokens


FROZEN_DT = datetime(2026, 9, 2, 14, 30, 5)


@pytest.fixture(autouse=True)
def freeze_time():
    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT
        # Make datetime(2026, ...) still work for real datetime construction
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        yield mock_dt


# --- {date} ---

def test_date_token_expands_to_YYYY_MM_DD():
    result = expand_filename_tokens("{date}-notes.md")
    assert result == "2026-09-02-notes.md"


def test_date_token_only():
    result = expand_filename_tokens("{date}.md")
    assert result == "2026-09-02.md"


# --- {time} ---

def test_time_token_expands_to_HHMMSS():
    result = expand_filename_tokens("log-{time}.md")
    assert result == "log-143005.md"


# --- {datetime} ---

def test_datetime_token_expands_correctly():
    result = expand_filename_tokens("{datetime}.md")
    assert result == "2026-09-02T143005.md"


# --- {slug} ---

def test_slug_expands_from_title():
    result = expand_filename_tokens("{slug}.md", title="My Great Note")
    assert result == "my-great-note.md"


def test_slug_strips_special_chars():
    result = expand_filename_tokens("{slug}.md", title="Hello, World!")
    assert result == "hello-world.md"


def test_slug_collapses_spaces_to_hyphens():
    result = expand_filename_tokens("{slug}.md", title="  multiple   spaces  ")
    assert result == "multiple-spaces.md"


def test_slug_with_no_title_removes_token_cleanly():
    """With no title, {slug} is removed and surrounding hyphens are cleaned up."""
    result = expand_filename_tokens("{slug}-notes.md", title=None)
    assert result == "notes.md"


def test_slug_at_end_with_no_title_removes_cleanly():
    result = expand_filename_tokens("notes-{slug}.md", title=None)
    assert result == "notes.md"


def test_slug_in_middle_with_no_title_removes_cleanly():
    result = expand_filename_tokens("prefix-{slug}-suffix.md", title=None)
    assert result == "prefix-suffix.md"


# --- Literal (no tokens) ---

def test_literal_filename_returned_unchanged():
    result = expand_filename_tokens("my-note.md")
    assert result == "my-note.md"


# --- Combined tokens ---

def test_date_and_slug_combined():
    result = expand_filename_tokens("{date}-{slug}.md", title="weekly review")
    assert result == "2026-09-02-weekly-review.md"


def test_date_slug_missing_title_produces_clean_filename():
    result = expand_filename_tokens("{date}-{slug}.md", title=None)
    assert result == "2026-09-02.md"
