"""Slice B — TDD tests for resolve_storage (RED before implementation)."""
import pytest
from pathlib import Path

from note_writer.interfaces.mcp import resolve_storage
from note_writer.domain.config.models import Config
from note_writer.domain.config.resolver import PathResolver


@pytest.fixture
def tmp_resolver(tmp_path):
    return PathResolver(app_root=tmp_path)


@pytest.fixture
def config(tmp_path):
    return Config(storage={"inbox": str(tmp_path / "inbox"), "reviews": str(tmp_path / "reviews")})


# --- Alias route ---

def test_known_alias_resolves_to_path(config, tmp_resolver, tmp_path):
    result = resolve_storage("inbox", config, tmp_resolver)
    assert result == tmp_path / "inbox"


def test_another_known_alias(config, tmp_resolver, tmp_path):
    result = resolve_storage("reviews", config, tmp_resolver)
    assert result == tmp_path / "reviews"


def test_unknown_alias_raises_value_error(config, tmp_resolver):
    with pytest.raises(ValueError, match="Storage alias 'ghost' not found"):
        resolve_storage("ghost", config, tmp_resolver)


# --- Path route ---

def test_absolute_path_is_resolved_directly(config, tmp_resolver, tmp_path):
    abs_path = str(tmp_path / "some" / "other" / "folder")
    result = resolve_storage(abs_path, config, tmp_resolver)
    assert result == Path(abs_path)


def test_relative_path_with_slash_resolves_via_resolver(config, tmp_resolver, tmp_path):
    result = resolve_storage("sub/folder", config, tmp_resolver)
    assert result == (tmp_path / "sub" / "folder").resolve()


def test_tilde_path_is_treated_as_path_not_alias(config, tmp_resolver):
    result = resolve_storage("~/notes", config, tmp_resolver)
    assert result.is_absolute()
    assert "notes" in str(result)
