class NoteWriterError(Exception):
    """Base exception for all domain errors."""
    pass

class ConfigurationError(NoteWriterError):
    """Raised when configuration is invalid or cannot be loaded."""
    pass

class StorageNotFoundError(NoteWriterError):
    """Raised when a storage alias is not found in configuration."""
    pass

class TemplateNotFoundError(NoteWriterError):
    """Raised when a template alias is not found in configuration."""
    pass
