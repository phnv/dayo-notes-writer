import pytest
from pathlib import Path
from note_writer.domain.config.loader import load_config_from_file
from note_writer.domain.errors import ConfigurationError

def test_load_config_from_yaml(tmp_path: Path):
    yaml_content = """
    templates:
      daily: templates/daily.md
    bundles:
      daily:
        template: daily
        storage: inbox
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content)

    config = load_config_from_file(config_path)
    assert config.templates["daily"] == "templates/daily.md"
    assert config.bundles["daily"].storage == "inbox"

def test_load_config_raises_on_invalid_yaml(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("invalid: yaml: :")

    with pytest.raises(ConfigurationError):
        load_config_from_file(config_path)

def test_load_config_raises_on_invalid_schema(tmp_path: Path):
    yaml_content = """
    bundles:
      daily:
        # missing template and storage
        prompt: clean
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content)

    with pytest.raises(ConfigurationError):
        load_config_from_file(config_path)
