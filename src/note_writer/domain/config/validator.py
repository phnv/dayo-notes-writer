from pydantic import ValidationError
from note_writer.domain.errors import ConfigurationError
from note_writer.domain.config.models import Config

def validate_config(data: dict) -> Config:
    try:
        return Config(**data)
    except ValidationError as e:
        raise ConfigurationError(f"Configuration schema validation failed: {e}")
