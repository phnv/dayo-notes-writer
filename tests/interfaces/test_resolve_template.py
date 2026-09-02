"""Slice C — TDD tests for resolve_template (RED before implementation)."""
import pytest
from pathlib import Path

from note_writer.interfaces.mcp import resolve_template
from note_writer.domain.config.models import Config
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem


@pytest.fixture
def tmp_resolver(tmp_path):
    return PathResolver(app_root=tmp_path)


@pytest.fixture
def fs():
    return PathlibFilesystem()


@pytest.fixture
def templates_dir(tmp_path):
    d = tmp_path / "templates"
    d.mkdir()
    (d / "weekly.md").write_text("# Weekly Template", encoding="utf-8")
    return d


@pytest.fixture
def config(tmp_path):
    # Config stores template paths relative to project root
    return Config(templates={"weekly": "templates/weekly.md"})


# --- Alias route ---

def test_known_alias_returns_content(config, tmp_resolver, templates_dir, fs):
    result = resolve_template("weekly", config, tmp_resolver, templates_dir, fs)
    assert result == "# Weekly Template"


def test_unknown_alias_raises_value_error(config, tmp_resolver, templates_dir, fs):
    with pytest.raises(ValueError, match="Template alias 'missing' not found"):
        resolve_template("missing", config, tmp_resolver, templates_dir, fs)


# --- Path route ---

def test_absolute_path_returns_content(config, tmp_resolver, templates_dir, fs):
    file_path = templates_dir / "weekly.md"
    result = resolve_template(str(file_path), config, tmp_resolver, templates_dir, fs)
    assert result == "# Weekly Template"


def test_path_to_nonexistent_file_raises(config, tmp_resolver, templates_dir, fs, tmp_path):
    bad_path = str(tmp_path / "nonexistent.md")
    with pytest.raises(ValueError, match="Template file not found"):
        resolve_template(bad_path, config, tmp_resolver, templates_dir, fs)


def test_unknown_alias_raises_not_path_error(config, tmp_resolver, templates_dir, fs):
    """An alias-looking value (no separator) that is not in config raises cleanly."""
    with pytest.raises(ValueError, match="Template alias 'unknown_alias' not found"):
        resolve_template("unknown_alias", config, tmp_resolver, templates_dir, fs)
