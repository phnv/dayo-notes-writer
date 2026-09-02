"""Unit tests for resolve_args -- the three-tier argument resolution pipeline."""
import pytest
from pathlib import Path

from note_writer.interfaces.mcp import resolve_args, AppState
from note_writer.domain.config.models import Config, BundleConfig
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem


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

def test_explicit_storage_alias_overrides_bundle(state_with_bundle):
    """An explicit storage_alias must not be overwritten by the bundle storage."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", storage_alias="reviews")
    assert result["storage_alias"] == "reviews"


def test_explicit_template_overrides_bundle(state_with_bundle):
    """An explicit template must not be overwritten by the bundle template."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", template="meeting")
    assert result["template"] == "meeting"


# --- Tier 2: named bundle fills missing args ---

def test_bundle_fills_missing_storage_alias(state_with_bundle):
    """When storage_alias is None, the bundle storage fills it in."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", storage_alias=None)
    assert result["storage_alias"] == "inbox"


def test_bundle_fills_missing_template(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle="my_bundle", template=None)
    assert result["template"] == "weekly"


def test_bundle_fills_missing_prompt(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle="my_bundle", prompt=None)
    assert result["prompt"] == "write"


def test_bundle_fills_storage_key_for_prompts(state_with_bundle):
    """For prompt functions using storage (not storage_alias), the key must still fill."""
    result = resolve_args(state_with_bundle, bundle="my_bundle", storage=None)
    assert result["storage"] == "inbox"


# --- Tier 3: defaults.bundle fallback ---

def test_defaults_bundle_fills_storage_alias_when_no_bundle_arg(state_with_bundle):
    """No explicit bundle arg => must fall back to defaults.bundle and fill storage_alias."""
    result = resolve_args(state_with_bundle, bundle=None, storage_alias=None)
    assert result["storage_alias"] == "inbox"


def test_defaults_bundle_fills_template_when_no_bundle_arg(state_with_bundle):
    result = resolve_args(state_with_bundle, bundle=None, template=None)
    assert result["template"] == "weekly"


def test_explicit_arg_still_wins_over_defaults_bundle(state_with_bundle):
    """Even with defaults.bundle active, an explicit arg must not be replaced."""
    result = resolve_args(state_with_bundle, bundle=None, storage_alias="reviews")
    assert result["storage_alias"] == "reviews"


# --- No bundle, no defaults: return unchanged ---

def test_no_bundle_no_defaults_returns_kwargs_unchanged(tmp_path):
    """When there is no bundle and no defaults, all-None kwargs pass through unchanged."""
    state = make_state(tmp_path, bundles={}, defaults={})
    result = resolve_args(state, bundle=None, storage_alias=None, template=None)
    assert result["storage_alias"] is None
    assert result["template"] is None


# --- Error cases ---

def test_invalid_named_bundle_raises(state_with_bundle):
    with pytest.raises(ValueError, match="not found in configuration"):
        resolve_args(state_with_bundle, bundle="nonexistent", storage_alias=None)


def test_invalid_defaults_bundle_raises(tmp_path):
    """If defaults.bundle names a bundle that does not exist, must raise ValueError."""
    state = make_state(tmp_path, bundles={}, defaults={"bundle": "ghost_bundle"})
    with pytest.raises(ValueError, match="not found in configuration"):
        resolve_args(state, bundle=None, storage_alias=None)
