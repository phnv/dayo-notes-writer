import yaml
from pathlib import Path
from note_writer.domain.errors import ConfigurationError
from note_writer.domain.config.models import Config
from note_writer.domain.config.validator import validate_config

def load_config_from_file(path: Path) -> Config:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Failed to parse YAML: {e}")
    except OSError as e:
        raise ConfigurationError(f"Failed to read file: {e}")

    if not isinstance(data, dict):
        raise ConfigurationError("Configuration file must contain a YAML object")

    return validate_config(data)
