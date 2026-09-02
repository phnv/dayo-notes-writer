"""Unit tests for resolve_args -- the three-tier argument resolution pipeline."""
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from note_writer.interfaces.mcp import resolve_args, AppState
from note_writer.domain.config.models import Config, BundleConfig
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem


FROZEN_DT = datetime(2026, 9, 2, 0, 0, 0)


def make_state(tmp_path, bundles=None, defaults=None):
    config = Config(
        storage={"inbox": str(tmp_path / "inbox"), "reviews": str(tmp_path / "reviews")},
        templates={"weekly": "templates/weekly.md", "meeting": "templates/meeting.md"},
        prompts={"write": "prompts/write.md"},
        bundles=bundles or {},
        defaults=defaults or {},
    )
    return AppState(
        config=config,
        fs=PathlibFilesystem(),
        resolver=PathResolver(app_root=tmp_path),
        prompts_dir=tmp_path / "prompts",
        templates_dir=tmp_path / "templates",
    )


@pytest.fixture
def bundle_cfg():
    return BundleConfig(template="weekly", prompt="write", storage="inbox")


@pytest.fixture
def state_with_bundle(tmp_path, bundle_cfg):
    return make_state(
        tmp_path,
        bundles={"my_bundle": bundle_cfg},
        defaults={"bundle": "my_bundle"},
    )


# --- Tier 1: explicit args always win ---

def test_explicit_storage_overrides_bundle(state_with_bundle):
    """An explicit storage must not be overwritten by the bundle storage."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", storage="reviews")
    assert result["storage"] == "reviews"


def test_explicit_template_overrides_bundle(state_with_bundle):
    """An explicit template must not be overwritten by the bundle template."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", template="meeting")
    assert result["template"] == "meeting"


def test_explicit_filename_overrides_bundle_filename(state_with_bundle):
    """An explicit filename must win over any bundle filename."""
    bundle_cfg_with_file = BundleConfig(
        template="weekly", prompt="write", storage="inbox", filename="{date}.md"
    )
    state = make_state(
        state_with_bundle.config.defaults.__class__.__new__(
            state_with_bundle.config.defaults.__class__
        )
    ) if False else make_state(
        Path(state_with_bundle.resolver.app_root),
        bundles={"b": bundle_cfg_with_file},
        defaults={"bundle": "b"},
    )
    result = resolve_args(state, bundle="b", filename="explicit.md")
    assert result["filename"] == "explicit.md"


# --- Tier 2: named bundle fills missing args ---

def test_bundle_fills_missing_storage(state_with_bundle):
    """When storage is None, the bundle storage fills it in."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", storage=None)
    assert result["storage"] == "inbox"


def test_bundle_fills_missing_template(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle="my_bundle", template=None)
    assert result["template"] == "weekly"


def test_bundle_fills_missing_prompt(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle="my_bundle", prompt=None)
    assert result["prompt"] == "write"


def test_bundle_fills_filename_when_present(tmp_path):
    """When bundle has filename and caller passes filename=None, bundle filename fills in."""
    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT
        bundle = BundleConfig(template="weekly", prompt="write", storage="inbox", filename="{date}-notes.md")
        state = make_state(tmp_path, bundles={"b": bundle}, defaults={})
        result = resolve_args(state, bundle="b", filename=None)
        assert result["filename"] == "2026-09-02-notes.md"


def test_bundle_filename_not_filled_when_key_absent(tmp_path):
    """When the caller does NOT pass filename kwarg (e.g. read_note), bundle filename is ignored."""
    bundle = BundleConfig(template="weekly", prompt="write", storage="inbox", filename="fixed.md")
    state = make_state(tmp_path, bundles={"b": bundle}, defaults={})
    result = resolve_args(state, bundle="b", storage=None)
    assert "filename" not in result


def test_bundle_filename_uses_slug_from_title(tmp_path):
    """When bundle filename has {slug} and title is passed, slug expands."""
    with patch("note_writer.interfaces.mcp.datetime") as mock_dt:
        mock_dt.now.return_value = FROZEN_DT
        bundle = BundleConfig(template="weekly", prompt="write", storage="inbox", filename="{slug}.md")
        state = make_state(tmp_path, bundles={"b": bundle}, defaults={})
        result = resolve_args(state, bundle="b", filename=None, title="My Note")
        assert result["filename"] == "my-note.md"


# --- Tier 3: defaults.bundle fallback ---

def test_defaults_bundle_fills_storage_when_no_bundle_arg(state_with_bundle):
    """No explicit bundle arg => must fall back to defaults.bundle and fill storage."""
    result = resolve_args(state_with_bundle, bundle=None, storage=None)
    assert result["storage"] == "inbox"


def test_defaults_bundle_fills_template_when_no_bundle_arg(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle=None, template=None)
    assert result["template"] == "weekly"


def test_explicit_arg_still_wins_over_defaults_bundle(state_with_bundle):
    """Even with defaults.bundle active, an explicit arg must not be replaced."""
    result = resolve_args(state_with_bundle, bundle=None, storage="reviews")
    assert result["storage"] == "reviews"


# --- No bundle, no defaults: return unchanged ---

def test_no_bundle_no_defaults_returns_kwargs_unchanged(tmp_path):
    """When there is no bundle and no defaults, all-None kwargs pass through unchanged."""
    state = make_state(tmp_path, bundles={}, defaults={})
    result = resolve_args(state, bundle=None, storage=None, template=None)
    assert result["storage"] is None
    assert result["template"] is None


# --- Error cases ---

def test_invalid_named_bundle_raises(state_with_bundle):
    with pytest.raises(ValueError, match="not found in configuration"):
        resolve_args(state_with_bundle, bundle="nonexistent", storage=None)


def test_invalid_defaults_bundle_raises(tmp_path):
    """If defaults.bundle names a bundle that does not exist, must raise ValueError."""
    state = make_state(tmp_path, bundles={}, defaults={"bundle": "ghost_bundle"})
    with pytest.raises(ValueError, match="not found in configuration"):
        resolve_args(state, bundle=None, storage=None)
